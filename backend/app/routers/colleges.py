import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.dependencies import DbSession, require_role
from app.models import College, CurriculumAssignment, Programme, RefreshSession, University, UniversityStatus, User, UserRole
from app.schemas import CollegeCreate, CollegeResponse, CollegeUpdate

router = APIRouter(prefix="/api/colleges", tags=["colleges"])


def college_query(db: DbSession):
    return db.query(College).options(
        joinedload(College.university),
        joinedload(College.reviewers),
    )


def college_response(db: DbSession, college: College) -> CollegeResponse:
    reviewer = next((user for user in college.reviewers if user.role == UserRole.REVIEWER), None)
    programme_count = db.query(func.count(Programme.id)).filter(Programme.college_id == college.id).scalar() or 0
    assignment_count = db.query(func.count(CurriculumAssignment.id)).filter(
        CurriculumAssignment.college_id == college.id
    ).scalar() or 0
    return CollegeResponse(
        id=college.id,
        university_id=college.university_id,
        university_name=college.university.name,
        name=college.name,
        code=college.code,
        address=college.address,
        state=college.state,
        district=college.district,
        contact_person=college.contact_person,
        contact_email=college.contact_email,
        phone_number=college.phone_number,
        website=college.website,
        status=college.status,
        reviewer_id=reviewer.id if reviewer else None,
        reviewer_name=reviewer.full_name if reviewer else None,
        reviewer_email=reviewer.email if reviewer else None,
        programme_count=programme_count,
        assignment_count=assignment_count,
        created_at=college.created_at,
    )


@router.get("", response_model=list[CollegeResponse])
def list_colleges(
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
    university_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, max_length=120),
    college_status: str | None = Query(default=None, alias="status", pattern="^(active|inactive)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[CollegeResponse]:
    query = college_query(db).join(University)
    if university_id:
        query = query.filter(College.university_id == university_id)
    if college_status:
        query = query.filter(College.status == college_status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(College.name.ilike(pattern), College.code.ilike(pattern), University.name.ilike(pattern)))
    colleges = query.order_by(University.name, College.name).offset(offset).limit(limit).all()
    return [college_response(db, college) for college in colleges]


@router.post("", response_model=CollegeResponse, status_code=status.HTTP_201_CREATED)
def create_college(
    payload: CollegeCreate,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CollegeResponse:
    university = db.get(University, payload.university_id)
    if university is None:
        raise HTTPException(status_code=404, detail="University not found")
    if university.status != UniversityStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Activate the university before adding colleges.")
    college = College(**payload.model_dump())
    db.add(college)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A college with this code already exists for the selected university.") from exc
    college = college_query(db).filter(College.id == college.id).one()
    return college_response(db, college)


@router.patch("/{college_id}", response_model=CollegeResponse)
def update_college(
    college_id: uuid.UUID,
    payload: CollegeUpdate,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CollegeResponse:
    college = college_query(db).filter(College.id == college_id).first()
    if college is None:
        raise HTTPException(status_code=404, detail="College not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "name" and value is None:
            raise HTTPException(status_code=422, detail="College name cannot be empty.")
        if field == "status" and value == "inactive":
            reviewer_ids = db.query(User.id).filter(User.college_id == college.id, User.role == UserRole.REVIEWER)
            db.query(RefreshSession).filter(RefreshSession.user_id.in_(reviewer_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.college_id == college.id, User.role == UserRole.REVIEWER).update(
                {User.is_active: False}, synchronize_session=False
            )
        setattr(college, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="College update conflicts with an existing record.") from exc
    college = college_query(db).filter(College.id == college.id).one()
    return college_response(db, college)
