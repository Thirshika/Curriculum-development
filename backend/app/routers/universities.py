import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.dependencies import CurrentUser, DbSession, require_role
from app.models import RefreshSession, University, UniversityStatus, User, UserRole
from app.schemas import UniversityCreate, UniversityResponse, UniversityStatusUpdate, UniversityUpdate

router = APIRouter(prefix="/api/universities", tags=["universities"])


@router.get("", response_model=list[UniversityResponse])
def list_universities(
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
    search: str | None = Query(default=None, max_length=120),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[UniversityResponse]:
    query = db.query(University).options(joinedload(University.reviewers))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(University.name.ilike(pattern), University.code.ilike(pattern)))
    universities = query.order_by(University.name).offset(offset).limit(limit).all()
    response = []
    for university in universities:
        reviewer = next((item for item in university.reviewers if item.role == UserRole.REVIEWER), None)
        response.append(
            UniversityResponse(
                id=university.id,
                name=university.name,
                code=university.code,
                address=university.address,
                contact_person=university.contact_person,
                contact_email=university.contact_email,
                phone_number=university.phone_number,
                logo_url=university.logo_url,
                status=university.status.value,
                created_at=university.created_at,
                reviewer_id=reviewer.id if reviewer else None,
                reviewer_name=reviewer.full_name if reviewer else None,
                reviewer_email=reviewer.email if reviewer else None,
            )
        )
    return response


@router.post("", response_model=UniversityResponse, status_code=status.HTTP_201_CREATED)
def create_university(
    payload: UniversityCreate,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> University:
    university = University(**payload.model_dump())
    db.add(university)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A university with this code already exists") from exc
    db.refresh(university)
    return university


@router.patch("/{university_id}", response_model=UniversityResponse)
def update_university(
    university_id: uuid.UUID,
    payload: UniversityUpdate,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> University:
    university = db.get(University, university_id)
    if university is None:
        raise HTTPException(status_code=404, detail="University not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "name" and value is None:
            raise HTTPException(status_code=422, detail="University name cannot be empty")
        setattr(university, field, value)
    db.commit()
    db.refresh(university)
    return university


@router.patch("/{university_id}/status", response_model=UniversityResponse)
def update_university_status(
    university_id: uuid.UUID,
    payload: UniversityStatusUpdate,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> University:
    university = db.get(University, university_id)
    if university is None:
        raise HTTPException(status_code=404, detail="University not found")
    university.status = UniversityStatus(payload.status)
    if university.status == UniversityStatus.INACTIVE:
        reviewer_ids = db.query(User.id).filter(
            User.university_id == university.id,
            User.role == UserRole.REVIEWER,
        )
        db.query(RefreshSession).filter(RefreshSession.user_id.in_(reviewer_ids)).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.university_id == university.id, User.role == UserRole.REVIEWER).update(
            {User.is_active: False}, synchronize_session=False
        )
    db.commit()
    db.refresh(university)
    return university
