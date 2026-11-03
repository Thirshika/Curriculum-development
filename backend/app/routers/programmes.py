import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.dependencies import DbSession, require_role
from app.models import College, Programme, ProgrammeLevel, ProgrammeStatus, University, User, UserRole
from app.schemas import ProgrammeCreate, ProgrammeResponse, ProgrammeUpdate

router = APIRouter(prefix="/api/programmes", tags=["programmes"])
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


def programme_query(db: DbSession):
    return db.query(Programme).options(
        joinedload(Programme.university),
        joinedload(Programme.college),
    )


def programme_response(programme: Programme) -> ProgrammeResponse:
    return ProgrammeResponse(
        id=programme.id,
        university_id=programme.university_id,
        college_id=programme.college_id,
        college_name=programme.college.name if programme.college else None,
        university_name=programme.university.name,
        university_code=programme.university.code,
        name=programme.name,
        degree_type=programme.degree_type,
        specialization=programme.specialization,
        level=programme.level.value,
        duration_years=programme.duration_years,
        semester_count=programme.semester_count,
        academic_year=programme.academic_year,
        qualification_level=programme.qualification_level,
        status=programme.status.value,
        created_at=programme.created_at,
        updated_at=programme.updated_at,
    )


@router.get("", response_model=list[ProgrammeResponse])
def list_programmes(
    db: DbSession,
    _admin: AdminUser,
    university_id: uuid.UUID | None = None,
    college_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, max_length=120),
    programme_status: str | None = Query(default=None, alias="status", pattern="^(active|inactive)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[ProgrammeResponse]:
    query = programme_query(db)
    if university_id:
        query = query.filter(Programme.university_id == university_id)
    if college_id:
        query = query.filter(Programme.college_id == college_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.join(University).filter(
            or_(
                Programme.name.ilike(pattern),
                Programme.degree_type.ilike(pattern),
                Programme.specialization.ilike(pattern),
                University.name.ilike(pattern),
            )
        )
    if programme_status:
        query = query.filter(Programme.status == programme_status)
    programmes = query.order_by(Programme.name).offset(offset).limit(limit).all()
    return [programme_response(programme) for programme in programmes]


@router.post("", response_model=ProgrammeResponse, status_code=201)
def create_programme(
    payload: ProgrammeCreate,
    db: DbSession,
    admin: AdminUser,
) -> ProgrammeResponse:
    university = db.get(University, payload.university_id)
    if university is None:
        raise HTTPException(status_code=404, detail="University not found")
    if university.status != "active":
        raise HTTPException(status_code=409, detail="Activate this university before creating a programme.")
    college = None
    if payload.college_id:
        college = db.query(College).filter(
            College.id == payload.college_id,
            College.university_id == university.id,
            College.status == "active",
        ).first()
        if college is None:
            raise HTTPException(status_code=422, detail="The selected college must be active and belong to this university.")
    programme = Programme(
        university_id=university.id,
        college_id=college.id if college else None,
        name=payload.name,
        degree_type=payload.degree_type,
        specialization=payload.specialization or None,
        level=ProgrammeLevel(payload.level.value),
        duration_years=payload.duration_years,
        semester_count=payload.semester_count,
        academic_year=payload.academic_year,
        qualification_level=payload.qualification_level or None,
        created_by=admin.id,
    )
    db.add(programme)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This university already has a programme with that name for the academic year",
        ) from exc
    return programme_response(programme_query(db).filter(Programme.id == programme.id).one())


@router.patch("/{programme_id}", response_model=ProgrammeResponse)
def update_programme(
    programme_id: uuid.UUID,
    payload: ProgrammeUpdate,
    db: DbSession,
    _admin: AdminUser,
) -> ProgrammeResponse:
    programme = programme_query(db).filter(Programme.id == programme_id).first()
    if programme is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    updates = payload.model_dump(exclude_unset=True)
    if "college_id" in updates and updates["college_id"] is not None:
        college = db.query(College).filter(
            College.id == updates["college_id"],
            College.university_id == programme.university_id,
            College.status == "active",
        ).first()
        if college is None:
            raise HTTPException(status_code=422, detail="The selected college must be active and belong to this programme's university.")
    for field, value in updates.items():
        if value is None and field in {"name", "degree_type", "level", "duration_years", "semester_count", "academic_year", "status"}:
            raise HTTPException(status_code=422, detail=f"{field} cannot be empty")
        if field == "level":
            value = ProgrammeLevel(value.value)
        if field == "status":
            value = ProgrammeStatus(value.value)
        if field in {"specialization", "qualification_level"} and value == "":
            value = None
        setattr(programme, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This university already has a programme with that name for the academic year",
        ) from exc
    return programme_response(programme_query(db).filter(Programme.id == programme_id).one())
