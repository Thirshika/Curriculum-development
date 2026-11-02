import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import joinedload

from app.config import settings
from app.credit_engine import ConstraintEvidence, validate_credit_plan
from app.curriculum_generation import (
    build_cited_evidence,
    build_credit_distribution,
    generate_curriculum_with_openai,
    validate_curriculum,
)
from app.dependencies import DbSession, require_role
from app.models import (
    CreditConstraint,
    CurriculumGenerationJob,
    Programme,
    ProgrammeRegulatoryMapping,
    RegulatoryDocument,
    RegulatoryDocumentStatus,
    RegulatoryRule,
    RuleVerificationStatus,
    User,
    UserRole,
)
from app.regulatory import cosine_similarity, local_embedding
from app.schemas import (
    CreditCheckResult,
    CurriculumDraftContent,
    CurriculumGenerationResponse,
    GeneratedCurriculumContent,
)

router = APIRouter(prefix="/api/ai-generation", tags=["ai-generation"])
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


def programme_query(db, programme_id: uuid.UUID) -> Programme | None:
    return (
        db.query(Programme)
        .options(
            joinedload(Programme.university),
            joinedload(Programme.regulatory_mappings).joinedload(ProgrammeRegulatoryMapping.document),
        )
        .filter(Programme.id == programme_id)
        .first()
    )


def retrieve_applicable_evidence(db, programme: Programme) -> list[dict]:
    document_ids = [
        mapping.document_id
        for mapping in programme.regulatory_mappings
        if mapping.document.status == RegulatoryDocumentStatus.READY
    ]
    if not document_ids:
        raise HTTPException(
            status_code=409,
            detail="Map at least one active regulatory source to this programme before generating a curriculum.",
        )

    rules = (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.document))
        .join(RegulatoryDocument)
        .filter(
            RegulatoryRule.document_id.in_(document_ids),
            RegulatoryRule.verification_status == RuleVerificationStatus.VERIFIED,
            RegulatoryRule.has_conflict.is_(False),
            RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
        )
        .all()
    )
    if not rules:
        raise HTTPException(
            status_code=409,
            detail="This programme has no verified, unconflicted rules in its active regulatory sources.",
        )

    level_terms = {
        "ug": "undergraduate",
        "pg": "postgraduate",
        "doctoral": "doctoral",
        "certificate": "certificate",
        "diploma": "diploma",
        "other": "programme",
    }
    query_vectors = [
        local_embedding(
            f"{programme.university.name} {programme.name} {programme.degree_type} "
            f"{programme.specialization or ''} curriculum structure outcomes assessment"
        ),
        local_embedding(
            f"{level_terms[programme.level.value]} programmes credits duration semesters"
        ),
        local_embedding(
            f"{programme.degree_type} course outcomes syllabus learning objectives"
        ),
    ]
    ranked = sorted(
        (
            (max(cosine_similarity(vector, rule.embedding) for vector in query_vectors), rule)
            for rule in rules
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    evidence = []
    for similarity, rule in ranked:
        if similarity <= 0:
            continue
        document = rule.document
        evidence.append(
            {
                "rule_id": str(rule.id),
                "document_id": str(document.id),
                "title": document.title,
                "category": document.category.value,
                "issuing_authority": document.issuing_authority,
                "version": document.version,
                "effective_date": document.effective_date.isoformat() if document.effective_date else None,
                "applicability": document.applicability,
                "clause": rule.clause,
                "page_number": rule.page_number,
                "text": rule.text,
                "similarity": round(similarity, 4),
            }
        )
        if len(evidence) == 12:
            break
    if not evidence:
        raise HTTPException(
            status_code=409,
            detail="No applicable regulatory evidence matched this programme. Review its mapped sources before generating.",
        )
    return evidence


def get_applicable_constraints(db, programme: Programme) -> list[ConstraintEvidence]:
    document_ids = [
        mapping.document_id
        for mapping in programme.regulatory_mappings
        if mapping.document.status == RegulatoryDocumentStatus.READY
    ]
    if not document_ids:
        return []
    rows = (
        db.query(CreditConstraint, RegulatoryRule, RegulatoryDocument)
        .join(RegulatoryRule, CreditConstraint.rule_id == RegulatoryRule.id)
        .join(RegulatoryDocument, RegulatoryRule.document_id == RegulatoryDocument.id)
        .filter(
            RegulatoryDocument.id.in_(document_ids),
            RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
            RegulatoryRule.verification_status == RuleVerificationStatus.VERIFIED,
            RegulatoryRule.has_conflict.is_(False),
        )
        .all()
    )
    return [
        ConstraintEvidence(
            rule_id=rule.id,
            document_id=document.id,
            document_title=document.title,
            clause=rule.clause,
            page_number=rule.page_number,
            version=document.version,
            kind=constraint.kind,
            value=constraint.value,
        )
        for constraint, rule, document in rows
    ]


def validation_for(curriculum: GeneratedCurriculumContent, programme: Programme, constraints: list[ConstraintEvidence]):
    semester_credits = [
        sum((course.credits for course in semester.courses), Decimal("0"))
        for semester in curriculum.semesters
    ]
    result_status, _total, checks = validate_credit_plan(
        duration_years=programme.duration_years,
        semester_count=programme.semester_count,
        semester_credits=semester_credits,
        constraints=constraints,
    )
    return result_status, checks


def generation_response(job: CurriculumGenerationJob) -> CurriculumGenerationResponse:
    return CurriculumGenerationResponse(
        id=job.id,
        programme_id=job.programme_id,
        status=job.status,
        model=job.model,
        curriculum=job.curriculum,
        regulatory_references=job.regulatory_references,
        validation_status=job.validation_status,
        validation_checks=[CreditCheckResult.model_validate(check) for check in job.validation_checks],
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
    evidence = retrieve_applicable_evidence(db, programme)
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
        generated = await generate_curriculum_with_openai(
            model=job.model,
            programme=programme_input,
            evidence=evidence,
        )
    except HTTPException as exc:
        job.status = "failed"
        job.failure_reason = exc.detail
        db.commit()
        raise

    try:
        validate_curriculum(
            generated,
            semester_count=programme.semester_count,
            retrieved_rule_ids={uuid.UUID(item["rule_id"]) for item in evidence},
        )
        final_content = CurriculumDraftContent.model_validate(response_content(generated))
        citations = build_cited_evidence(
            generated,
            {uuid.UUID(item["rule_id"]): item for item in evidence},
        )
    except (ValueError, ValidationError) as exc:
        job.status = "failed"
        job.failure_reason = "The generated curriculum failed structural or citation validation."
        db.commit()
        raise HTTPException(status_code=502, detail=job.failure_reason) from exc

    validation_status, checks = validation_for(generated, programme, get_applicable_constraints(db, programme))
    job.status = "completed"
    job.curriculum = final_content.model_dump(mode="json")
    job.regulatory_references = citations
    job.validation_status = validation_status
    job.validation_checks = checks
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
    evidence_by_id = {
        uuid.UUID(item["rule_id"]): item for item in job.regulatory_references
    }
    try:
        validate_curriculum(
            generated,
            semester_count=programme.semester_count,
            retrieved_rule_ids=set(evidence_by_id),
        )
        final_content = CurriculumDraftContent.model_validate(response_content(generated))
        citations = build_cited_evidence(generated, evidence_by_id)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    validation_status, checks = validation_for(generated, programme, get_applicable_constraints(db, programme))
    job.curriculum = final_content.model_dump(mode="json")
    job.regulatory_references = citations
    job.validation_status = validation_status
    job.validation_checks = checks
    db.commit()
    db.refresh(job)
    return generation_response(job)
