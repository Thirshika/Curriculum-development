import csv
import io
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import DbSession, require_role
from app.models import Course, User, UserRole
from app.routers.credit_table import get_credit_table
from app.schemas import CourseCategorySummary, CourseCreate, CourseCreditSummary, CourseImportResponse, CourseResponse, CourseUpdate

router = APIRouter(prefix="/api/courses", tags=["courses"])
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
CSV_MAX_BYTES = 5 * 1024 * 1024
CSV_MAX_ROWS = 2000


def course_response(course: Course) -> CourseResponse:
    return CourseResponse(
        id=course.id,
        course_code=course.course_code,
        name=course.name,
        category=course.category,
        semester=course.semester,
        lecture_hours=course.lecture_hours,
        tutorial_hours=course.tutorial_hours,
        practical_hours=course.practical_hours,
        credits=course.credits,
        status=course.status,
    )


def course_summary(db: Session, programme_level: str) -> CourseCreditSummary:
    courses = db.query(Course).filter(Course.status == "active").all()
    totals: dict[str, Decimal] = {}
    for course in courses:
        category = course.category.strip()
        totals[category] = totals.get(category, Decimal("0")) + course.credits
    category_limits = {
        row.category.casefold(): row
        for row in get_credit_table(db, programme_level).rows
        if row.scope_type == "category" and row.category
    }
    categories = []
    for name in sorted(set(totals) | {row.category for row in category_limits.values() if row.category}, key=str.casefold):
        used = totals.get(name, Decimal("0"))
        row = category_limits.get(name.casefold())
        minimum = row.minimum if row else None
        maximum = row.maximum if row else None
        if row and row.total is not None:
            minimum = minimum if minimum is not None else row.total
            maximum = maximum if maximum is not None else row.total
        if minimum is None and maximum is None:
            status = "not_configured"
        elif (minimum is not None and used < minimum) or (maximum is not None and used > maximum):
            status = "outside_limit"
        else:
            status = "within_limit"
        categories.append(CourseCategorySummary(
            category=name,
            used_credits=used,
            minimum=minimum,
            maximum=maximum,
            status=status,
        ))
    return CourseCreditSummary(
        programme_level=programme_level,
        categories=categories,
        total_credits=sum(totals.values(), Decimal("0")),
    )


@router.get("", response_model=list[CourseResponse])
def list_courses(
    db: DbSession,
    _admin: AdminUser,
    search: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=100),
    semester: int | None = Query(default=None, ge=1, le=24),
    course_status: str | None = Query(default=None, alias="status", pattern="^(active|archived)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[CourseResponse]:
    query = db.query(Course)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Course.course_code.ilike(pattern), Course.name.ilike(pattern)))
    if category:
        query = query.filter(Course.category.ilike(category.strip()))
    if semester:
        query = query.filter(Course.semester == semester)
    if course_status:
        query = query.filter(Course.status == course_status)
    query = query.order_by(Course.semester, Course.category, Course.course_code).offset(offset)
    query = query.limit(limit)
    return [course_response(course) for course in query.all()]


@router.get("/summary", response_model=CourseCreditSummary)
def get_course_summary(
    db: DbSession,
    _admin: AdminUser,
    programme_level: str = Query(default="ug", pattern="^(ug|pg)$"),
) -> CourseCreditSummary:
    return course_summary(db, programme_level)


@router.post("", response_model=CourseResponse, status_code=201)
def create_course(payload: CourseCreate, db: DbSession, admin: AdminUser) -> CourseResponse:
    course = Course(
        **payload.model_dump(),
        description="",
        objectives=[],
        prerequisites=[],
        programme_ids=[],
        status="active",
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


@router.post("/import", response_model=CourseImportResponse)
async def import_courses(
    db: DbSession,
    _admin: AdminUser,
    file: UploadFile = File(...),
) -> CourseImportResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a .csv file.")
    content = await file.read(CSV_MAX_BYTES + 1)
    if len(content) > CSV_MAX_BYTES:
        raise HTTPException(status_code=413, detail="The CSV exceeds the 5 MB upload limit.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="The CSV must be encoded as UTF-8.") from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {
        "course_code", "name", "category", "semester", "lecture_hours",
        "tutorial_hours", "practical_hours", "credits",
    }
    if not reader.fieldnames or not required.issubset({name.strip() for name in reader.fieldnames if name}):
        raise HTTPException(
            status_code=422,
            detail=f"CSV headers must include: {', '.join(sorted(required))}.",
        )
    raw_rows = list(reader)
    if len(raw_rows) > CSV_MAX_ROWS:
        raise HTTPException(status_code=413, detail=f"CSV files can contain at most {CSV_MAX_ROWS} courses.")
    existing_codes = {
        row[0].casefold()
        for row in db.query(Course.course_code).all()
    }
    seen_codes: set[str] = set()
    valid_rows: list[CourseCreate] = []
    errors: list[str] = []
    for index, row in enumerate(raw_rows, start=2):
        normalized = {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
        try:
            payload = CourseCreate.model_validate(normalized)
        except ValidationError as exc:
            errors.append(f"Row {index}: {exc}")
            continue
        code = payload.course_code.casefold()
        if code in existing_codes or code in seen_codes:
            errors.append(f"Row {index}: course code {payload.course_code} already exists.")
            continue
        seen_codes.add(code)
        valid_rows.append(payload)

    courses = [
        Course(
            **payload.model_dump(),
            description="",
            objectives=[],
            prerequisites=[],
            programme_ids=[],
            status="active",
            created_by=_admin.id,
        )
        for payload in valid_rows
    ]
    db.add_all(courses)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A course code conflicts with another catalogue entry.") from exc
    return CourseImportResponse(imported=len(courses), errors=errors)


@router.patch("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    db: DbSession,
    _admin: AdminUser,
) -> CourseResponse:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(course, field, value.upper() if field == "course_code" else value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A course with this course code already exists.") from exc
    db.refresh(course)
    return course_response(course)


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: uuid.UUID, db: DbSession, _admin: AdminUser) -> None:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()
