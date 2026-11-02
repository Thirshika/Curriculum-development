import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, or_
from sqlalchemy.exc import IntegrityError

from app.dependencies import DbSession, require_role
from app.models import Course, Programme, User, UserRole
from app.schemas import CourseCreate, CourseResponse, CourseUpdate

router = APIRouter(prefix="/api/courses", tags=["courses"])


def course_response(course: Course) -> CourseResponse:
    return CourseResponse.model_validate(course, from_attributes=True)


def validate_programmes(db: DbSession, programme_ids: list[uuid.UUID]) -> list[str]:
    ids = list(dict.fromkeys(programme_ids))
    if not ids:
        return []
    found = {row[0] for row in db.query(Programme.id).filter(Programme.id.in_(ids)).all()}
    if found != set(ids):
        raise HTTPException(status_code=422, detail="One or more mapped programmes do not exist.")
    return [str(item) for item in ids]


@router.get("", response_model=list[CourseResponse])
def list_courses(
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
    search: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=100),
    course_status: str | None = Query(default=None, alias="status", pattern="^(active|archived)$"),
    programme_id: uuid.UUID | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[CourseResponse]:
    query = db.query(Course)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Course.course_code.ilike(pattern), Course.name.ilike(pattern), Course.description.ilike(pattern)))
    if category:
        query = query.filter(Course.category == category)
    if course_status:
        query = query.filter(Course.status == course_status)
    if programme_id:
        query = query.filter(cast(Course.programme_ids, String).ilike(f"%{programme_id}%"))
    return [course_response(course) for course in query.order_by(Course.course_code).offset(offset).limit(limit).all()]


@router.post("", response_model=CourseResponse, status_code=201)
def create_course(
    payload: CourseCreate,
    db: DbSession,
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CourseResponse:
    values = payload.model_dump(exclude={"programme_ids"})
    course = Course(
        **values,
        programme_ids=validate_programmes(db, payload.programme_ids),
        created_by=admin.id,
    )
    db.add(course)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A course with this course code already exists.") from exc
    db.refresh(course)
    return course_response(course)


@router.patch("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CourseResponse:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    updates = payload.model_dump(exclude_unset=True)
    if "programme_ids" in updates:
        updates["programme_ids"] = validate_programmes(db, updates["programme_ids"] or [])
    for field, value in updates.items():
        if value is not None:
            setattr(course, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Course update conflicts with another catalogue entry.") from exc
    db.refresh(course)
    return course_response(course)


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(
    course_id: uuid.UUID,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CourseResponse:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course_response(course)
