import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.dependencies import DbSession, require_role
from app.models import College, RefreshSession, University, UniversityStatus, User, UserRole
from app.schemas import (
    ReviewerCreate,
    ReviewerPasswordReset,
    ReviewerResponse,
    ReviewerUpdate,
)
from app.security import hash_password

router = APIRouter(prefix="/api/reviewers", tags=["reviewers"])


def reviewer_response(reviewer: User) -> ReviewerResponse:
    if reviewer.university is None:
        raise HTTPException(status_code=409, detail="Reviewer account has no assigned university")
    return ReviewerResponse(
        id=reviewer.id,
        email=reviewer.email,
        username=reviewer.username or reviewer.university.code,
        full_name=reviewer.full_name,
        university_id=reviewer.university_id,
        university_name=reviewer.university.name,
        university_code=reviewer.university.code,
        college_id=reviewer.college_id,
        college_name=reviewer.college.name if reviewer.college else None,
        is_active=reviewer.is_active,
        must_change_password=reviewer.must_change_password,
        created_at=reviewer.created_at,
    )


@router.get("", response_model=list[ReviewerResponse])
def list_reviewers(
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
    search: str | None = Query(default=None, max_length=120),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[ReviewerResponse]:
    query = (
        db.query(User)
        .options(joinedload(User.university), joinedload(User.college))
        .filter(User.role == UserRole.REVIEWER)
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.join(University).filter(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                University.name.ilike(pattern),
                University.code.ilike(pattern),
                College.name.ilike(pattern),
                College.code.ilike(pattern),
            )
        )
    reviewers = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return [reviewer_response(reviewer) for reviewer in reviewers]


@router.post("", response_model=ReviewerResponse, status_code=status.HTTP_201_CREATED)
def create_reviewer(
    payload: ReviewerCreate,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> ReviewerResponse:
    university = db.get(University, payload.university_id)
    if university is None:
        raise HTTPException(status_code=404, detail="University not found")
    if university.status != UniversityStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Activate this university before assigning a reviewer")
    college = None
    username = university.code
    if payload.college_id:
        college = db.query(College).filter(
            College.id == payload.college_id,
            College.university_id == university.id,
        ).first()
        if college is None:
            raise HTTPException(status_code=422, detail="The selected college must belong to this university.")
        if college.status != "active":
            raise HTTPException(status_code=409, detail="Activate the college before assigning its reviewer.")
        if db.query(User.id).filter(User.college_id == college.id, User.role == UserRole.REVIEWER).first():
            raise HTTPException(status_code=409, detail="This college already has a reviewer account.")
        username = f"{university.code}-{college.code}"[:64]
    elif db.query(User.id).filter(
        User.university_id == university.id,
        User.role == UserRole.REVIEWER,
        User.college_id.is_(None),
    ).first():
        raise HTTPException(status_code=409, detail="This university already has a university-wide reviewer account.")
    reviewer = User(
        email=str(payload.email).lower(),
        username=username,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.REVIEWER,
        university_id=university.id,
        college_id=college.id if college else None,
        must_change_password=False,
    )
    db.add(reviewer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This email, reviewer ID, or college already has a reviewer account") from exc
    db.refresh(reviewer)
    reviewer.university = university
    reviewer.college = college
    return reviewer_response(reviewer)


@router.patch("/{reviewer_id}", response_model=ReviewerResponse)
def update_reviewer(
    reviewer_id: uuid.UUID,
    payload: ReviewerUpdate,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> ReviewerResponse:
    reviewer = (
        db.query(User)
        .options(joinedload(User.university), joinedload(User.college))
        .filter(User.id == reviewer_id, User.role == UserRole.REVIEWER)
        .first()
    )
    if reviewer is None:
        raise HTTPException(status_code=404, detail="Reviewer not found")
    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates:
        reviewer.email = str(updates.pop("email")).lower()
    if "is_active" in updates:
        is_active = updates.pop("is_active")
        if is_active and reviewer.university.status != UniversityStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="Activate the university before activating its reviewer")
        reviewer.is_active = is_active
        if not is_active:
            db.query(RefreshSession).filter(RefreshSession.user_id == reviewer.id).delete()
    for field, value in updates.items():
        setattr(reviewer, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A user with this email already exists") from exc
    db.refresh(reviewer)
    return reviewer_response(reviewer)


@router.post("/{reviewer_id}/reset-password", response_model=ReviewerResponse)
def reset_reviewer_password(
    reviewer_id: uuid.UUID,
    payload: ReviewerPasswordReset,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> ReviewerResponse:
    reviewer = db.query(User).filter(User.id == reviewer_id, User.role == UserRole.REVIEWER).first()
    if reviewer is None:
        raise HTTPException(status_code=404, detail="Reviewer not found")
    reviewer.password_hash = hash_password(payload.password)
    reviewer.must_change_password = False
    db.query(RefreshSession).filter(RefreshSession.user_id == reviewer.id).delete()
    db.commit()
    db.refresh(reviewer)
    return reviewer_response(reviewer)
