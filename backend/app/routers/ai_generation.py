import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from app.config import settings
from app.curriculum_generation import build_credit_distribution, generate_curriculum_with_openai, validate_curriculum
from app.dependencies import DbSession, require_role
from app.models import CurriculumGenerationJob, Programme, User, UserRole
from app.schemas import CurriculumDraftContent, CurriculumGenerationResponse, GeneratedCurriculumContent

router = APIRouter(prefix="/api/ai-generation", tags=["ai-generation"])
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


def programme_query(db: DbSession, programme_id: uuid.UUID) -> Programme | None:
    return db.query(Programme).filter(Programme.id == programme_id).first()


def generation_response(job: CurriculumGenerationJob) -> CurriculumGenerationResponse:
    return CurriculumGenerationResponse(
        id=job.id,
        programme_id=job.programme_id,
        status=job.status,
        model=job.model,
        curriculum=job.curriculum,
        failure_reason=job.failure_reason,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def response_content(curriculum: GeneratedCurriculumContent) -> dict:
    payload = curriculum.model_dump(mode="json")
    payload["credit_distribution"] = build_credit_distribution(curriculum)
    return payload


@router.post(
    "/programmes/{programme_id}",
    response_model=CurriculumGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_programme_curriculum(
    programme_id: uuid.UUID,
    db: DbSession,
    admin: AdminUser,
) -> CurriculumGenerationResponse:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Curriculum generation is unavailable until OPENAI_API_KEY is configured on the backend.",
        )
    programme = programme_query(db, programme_id)
    if programme is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    if programme.status != "active":
        raise HTTPException(status_code=409, detail="Activate this programme before generating a curriculum.")
    job = CurriculumGenerationJob(
        programme_id=programme.id,
        created_by=admin.id,
        status="generating",
        model=settings.openai_model,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    programme_input = {
        "university": programme.university.name,
        "programme_name": programme.name,
        "degree_type": programme.degree_type,
        "specialization": programme.specialization,
        "level": programme.level.value,
        "duration_years": str(programme.duration_years),
        "semester_count": programme.semester_count,
        "academic_year": programme.academic_year,
        "qualification_level": programme.qualification_level,
    }
    try:
        generated = await generate_curriculum_with_openai(model=job.model, programme=programme_input)
        validate_curriculum(generated, semester_count=programme.semester_count)
        final_content = CurriculumDraftContent.model_validate(response_content(generated))
    except HTTPException as exc:
        job.status = "failed"
        job.failure_reason = exc.detail
        db.commit()
        raise
    except (ValueError, ValidationError) as exc:
        job.status = "failed"
        job.failure_reason = "The generated curriculum failed structural validation."
        db.commit()
        raise HTTPException(status_code=502, detail=job.failure_reason) from exc

    job.status = "completed"
    job.curriculum = final_content.model_dump(mode="json")
    job.regulatory_references = []
    job.validation_status = "not_run"
    job.validation_checks = []
    db.commit()
    db.refresh(job)
    return generation_response(job)


@router.get(
    "/programmes/{programme_id}",
    response_model=list[CurriculumGenerationResponse],
)
def list_programme_generations(
    programme_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[CurriculumGenerationResponse]:
    if db.query(Programme.id).filter(Programme.id == programme_id).first() is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    jobs = (
        db.query(CurriculumGenerationJob)
        .filter(CurriculumGenerationJob.programme_id == programme_id)
        .order_by(CurriculumGenerationJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [generation_response(job) for job in jobs]


@router.get("/{job_id}", response_model=CurriculumGenerationResponse)
def get_generation(
    job_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
) -> CurriculumGenerationResponse:
    job = db.get(CurriculumGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Curriculum generation job not found")
    return generation_response(job)


@router.patch("/{job_id}", response_model=CurriculumGenerationResponse)
def update_generation(
    job_id: uuid.UUID,
    payload: CurriculumDraftContent,
    db: DbSession,
    _admin: AdminUser,
) -> CurriculumGenerationResponse:
    job = db.get(CurriculumGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Curriculum generation job not found")
    if job.status != "completed" or not job.curriculum:
        raise HTTPException(status_code=409, detail="Only completed curriculum drafts can be edited.")
    programme = programme_query(db, job.programme_id)
    generated = GeneratedCurriculumContent.model_validate(payload.model_dump(exclude={"credit_distribution"}))
    try:
        validate_curriculum(generated, semester_count=programme.semester_count)
        final_content = CurriculumDraftContent.model_validate(response_content(generated))
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job.curriculum = final_content.model_dump(mode="json")
    job.regulatory_references = []
    job.validation_status = "not_run"
    job.validation_checks = []
    db.commit()
    db.refresh(job)
    return generation_response(job)
