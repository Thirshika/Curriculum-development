import csv
import io
import re
import uuid
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.dependencies import DbSession, require_role
from app.models import Course, Programme, User, UserRole
from app.routers.credit_table import _degree_credit_table, get_credit_table
from app.schemas import (
    CourseCatalogueRow,
    CourseCategorySummary,
    CourseCreate,
    CourseCreditDefaultResponse,
    CourseCreditSummary,
    CourseImportResponse,
    CourseLibraryDetail,
    CourseLibraryPaperResponse,
    CourseLibrarySave,
    CourseLibrarySemesterSummary,
    CourseResponse,
    CourseUpdate,
)

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
        course_type=course.course_type,
        lecture_hours=course.lecture_hours,
        tutorial_hours=course.tutorial_hours,
        practical_hours=course.practical_hours,
        internal_marks=course.internal_marks,
        external_marks=course.external_marks,
        total_marks=course.internal_marks + course.external_marks,
        credits=course.credits,
        status=course.status,
        programme_id=course.programme_id,
    )


def programme_courses(db: Session, programme: Programme, include_archived: bool = False) -> list[Course]:
    candidates = db.query(Course).filter(
        or_(Course.programme_id == programme.id, Course.programme_id.is_(None))
    ).all()
    programme_id = str(programme.id)
    return sorted(
        (
            course
            for course in candidates
            if (
                course.programme_id == programme.id
                or programme_id in (course.programme_ids or [])
            )
            and (include_archived or course.status != "archived")
        ),
        key=lambda course: (course.semester, course.course_code.casefold()),
    )


def library_detail(db: Session, programme: Programme) -> CourseLibraryDetail:
    papers = programme_courses(
        db,
        programme,
        include_archived=programme.catalogue_status == "archived",
    )
    papers = [paper for paper in papers if paper.status in {"active", "draft", "archived"}]
    visible_papers = papers if programme.catalogue_status == "archived" else [
        paper for paper in papers if paper.status != "archived"
    ]
    summaries = []
    for semester_number in range(1, programme.semester_count + 1):
        semester_papers = [
            paper for paper in visible_papers if paper.semester == semester_number
        ]
        summaries.append(CourseLibrarySemesterSummary(
            semester=semester_number,
            total_papers=len(semester_papers),
            total_credits=sum((paper.credits for paper in semester_papers), Decimal("0")),
        ))
    return CourseLibraryDetail(
        programme_id=programme.id,
        course_name=programme.catalogue_course_name or programme.name,
        course_code=programme.catalogue_course_code or "",
        university_id=programme.university_id,
        university=programme.university.name,
        programme=programme.name,
        course_level=programme.level.value,
        duration_years=programme.duration_years,
        total_semesters=programme.semester_count,
        total_papers=len(visible_papers),
        total_credits=sum((paper.credits for paper in visible_papers), Decimal("0")),
        status=programme.catalogue_status or "draft",
        configured=programme.catalogue_course_code is not None,
        faculty_school=programme.faculty_school or (programme.college.name if programme.college else ""),
        department=programme.department or "",
        description=programme.course_description or "",
        regulation_year=programme.regulation_year or "",
        academic_year=programme.academic_year,
        effective_from=programme.effective_from,
        effective_until=programme.effective_until,
        semesters=summaries,
        papers=[
            CourseLibraryPaperResponse(
                id=paper.id,
                semester=paper.semester,
                paper_code=paper.course_code,
                paper_title=paper.name,
                paper_type=paper.course_type,
                category=paper.category,
                lecture_hours=paper.lecture_hours,
                tutorial_hours=paper.tutorial_hours,
                practical_hours=paper.practical_hours,
                internal_marks=paper.internal_marks,
                external_marks=paper.external_marks,
                total_marks=paper.internal_marks + paper.external_marks,
                credits=paper.credits,
            )
            for paper in visible_papers
        ],
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
    course_status: str | None = Query(default=None, alias="status", pattern="^(active|draft|archived)$"),
    programme_id: uuid.UUID | None = None,
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
    if programme_id:
        query = query.filter(or_(Course.programme_id == programme_id, Course.programme_id.is_(None)))
        matched = [
            course for course in query.all()
            if course.programme_id == programme_id or str(programme_id) in (course.programme_ids or [])
        ]
        matched.sort(key=lambda course: (course.semester, course.category.casefold(), course.course_code.casefold()))
        return [course_response(course) for course in matched[offset:offset + limit]]
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


SEMESTER_CREDIT_DISTRIBUTION: dict[str, tuple[Decimal, list[int]]] = {
    "core (cc)": (Decimal("4"), [2, 2, 2, 3, 3, 3]),
    "core": (Decimal("4"), [2, 2, 2, 3, 3, 3]),
    "major": (Decimal("4"), [2, 2, 2, 3, 3, 3]),
    "major (core)": (Decimal("4"), [2, 2, 2, 3, 3, 3]),
    "minor (mi)": (Decimal("4"), [0, 1, 1, 1, 1, 2]),
    "minor": (Decimal("4"), [0, 1, 1, 1, 1, 2]),
    "minor stream": (Decimal("4"), [0, 1, 1, 1, 1, 2]),
    "multidisciplinary (mdc)": (Decimal("3"), [1, 1, 1, 0, 0, 0]),
    "multidisciplinary": (Decimal("3"), [1, 1, 1, 0, 0, 0]),
    "mdc": (Decimal("3"), [1, 1, 1, 0, 0, 0]),
    "aec": (Decimal("3"), [2, 2, 0, 0, 0, 0]),
    "ability enhancement": (Decimal("3"), [2, 2, 0, 0, 0, 0]),
    "ability enhancement courses (aec)": (Decimal("3"), [2, 2, 0, 0, 0, 0]),
    "sec": (Decimal("3"), [0, 0, 1, 1, 1, 0]),
    "skill enhancement": (Decimal("3"), [0, 0, 1, 1, 1, 0]),
    "skill enhancement courses (sec)": (Decimal("3"), [0, 0, 1, 1, 1, 0]),
    "skill-based": (Decimal("3"), [0, 0, 1, 1, 1, 0]),
    "vac": (Decimal("3"), [1, 1, 0, 0, 0, 0]),
    "value added": (Decimal("3"), [1, 1, 0, 0, 0, 0]),
    "value-added": (Decimal("3"), [1, 1, 0, 0, 0, 0]),
    "internship (int)": (Decimal("4"), [0, 0, 0, 0, 0, 1]),
    "internship": (Decimal("4"), [0, 0, 0, 0, 0, 1]),
    "research project": (Decimal("4"), [0, 0, 0, 0, 0, 1]),
}


@router.get("/credits/default", response_model=CourseCreditDefaultResponse)
def get_course_credit_default(
    db: DbSession,
    _admin: AdminUser,
    programme_id: uuid.UUID,
    category: str = Query(min_length=2, max_length=100),
    semester: int | None = Query(default=None, ge=1, le=24),
) -> CourseCreditDefaultResponse:
    programme = db.get(Programme, programme_id)
    if programme is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    if programme.level.value not in {"ug", "pg"}:
        raise HTTPException(status_code=422, detail="The existing Credit Table supports UG and PG programmes.")
    duration = int(programme.duration_years) if programme.duration_years % 1 == 0 else None
    table = (
        _degree_credit_table(db, programme.level.value, duration)
        if duration in {3, 4}
        else get_credit_table(db, programme.level.value)
    )
    row = next(
        (
            item for item in table.rows
            if item.scope_type == "category"
            and item.category
            and item.category.casefold() == category.strip().casefold()
        ),
        None,
    )
    default_credits = None
    source = None
    if row and row.credit_value:
        try:
            candidate = Decimal(row.credit_value)
            if candidate > 0:
                default_credits = candidate
                source = "Credit Table"
        except InvalidOperation:
            pass

    if default_credits is None:
        sem_rule = SEMESTER_CREDIT_DISTRIBUTION.get(category.strip().casefold())
        if sem_rule:
            default_credits = sem_rule[0]
            if semester and 1 <= semester <= len(sem_rule[1]):
                paper_cnt = sem_rule[1][semester - 1]
                tot = paper_cnt * default_credits
                source = (
                    f"Credit Table semester distribution (Semester {semester}): "
                    f"{paper_cnt} paper(s) = {tot} credits total → {default_credits} cr/paper"
                )
            else:
                source = f"Credit Table semester distribution ({default_credits} cr/paper)"

    return CourseCreditDefaultResponse(
        category=category.strip(),
        default_credits=default_credits,
        minimum=row.minimum if row else None,
        maximum=row.maximum if row else None,
        source=(
            source
            if default_credits is not None
            else "No fixed paper credit is configured in the Credit Table; enter the approved value."
        ),
    )


@router.get("/library", response_model=list[CourseCatalogueRow])
def list_course_library(
    db: DbSession,
    _admin: AdminUser,
    status: str | None = Query(default=None, pattern="^(draft|active|archived)$"),
    search: str | None = Query(default=None, max_length=120),
) -> list[CourseCatalogueRow]:
    query = db.query(Programme).options(
        joinedload(Programme.university),
        joinedload(Programme.college),
    ).filter(Programme.catalogue_course_code.is_not(None))
    if status:
        query = query.filter(Programme.catalogue_status == status)
    else:
        query = query.filter(Programme.catalogue_status != "archived")
    programmes = query.order_by(Programme.updated_at.desc()).all()
    rows = []
    for programme in programmes:
        detail = library_detail(db, programme)
        if search and not any(
            search.strip().casefold() in value.casefold()
            for value in (detail.course_name, detail.course_code, detail.university, detail.programme)
        ):
            continue
        rows.append(CourseCatalogueRow(**detail.model_dump(exclude={
            "configured", "faculty_school", "department", "description", "regulation_year",
            "academic_year", "effective_from", "effective_until", "semesters", "papers",
        })))
    return rows


@router.get("/library/{programme_id}", response_model=CourseLibraryDetail)
def get_course_library_detail(
    programme_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
) -> CourseLibraryDetail:
    programme = db.query(Programme).options(
        joinedload(Programme.university),
        joinedload(Programme.college),
    ).filter(Programme.id == programme_id).first()
    if programme is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    return library_detail(db, programme)


@router.put("/library/{programme_id}", response_model=CourseLibraryDetail)
def save_course_library(
    programme_id: uuid.UUID,
    payload: CourseLibrarySave,
    db: DbSession,
    admin: AdminUser,
) -> CourseLibraryDetail:
    programme = db.query(Programme).options(
        joinedload(Programme.university),
        joinedload(Programme.college),
    ).filter(Programme.id == programme_id).first()
    if programme is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    prog_year = re.sub(r"^(20\d{2})-(\d{2})$", r"\1-20\2", programme.academic_year.strip())
    if payload.academic_year != prog_year and payload.academic_year != programme.academic_year:
        raise HTTPException(status_code=422, detail="Academic Year must match the selected programme.")
    if payload.status == "active" and not payload.papers:
        raise HTTPException(status_code=422, detail="Add at least one paper before saving an active course.")
    if any(paper.semester > programme.semester_count for paper in payload.papers):
        raise HTTPException(
            status_code=422,
            detail=f"Papers must be assigned to one of the programme's {programme.semester_count} semesters.",
        )
    if len({paper.paper_code.casefold() for paper in payload.papers}) != len(payload.papers):
        raise HTTPException(status_code=422, detail="Paper codes must be unique within the course.")
    code_owner = any(
        existing.catalogue_course_code
        and existing.catalogue_course_code.casefold() == payload.course_code.casefold()
        for existing in db.query(Programme).filter(
            Programme.university_id == programme.university_id,
            Programme.id != programme.id,
        ).all()
    )
    if code_owner:
        raise HTTPException(status_code=409, detail="This course code is already used by another course at the university.")

    current_papers = programme_courses(db, programme, include_archived=True)
    current_by_id = {paper.id: paper for paper in current_papers}
    submitted_ids = [paper.id for paper in payload.papers if paper.id is not None]
    if len(set(submitted_ids)) != len(submitted_ids):
        raise HTTPException(status_code=422, detail="A paper cannot appear more than once.")
    for paper_id in submitted_ids:
        if paper_id not in current_by_id:
            raise HTTPException(status_code=422, detail="A submitted paper does not belong to this programme.")

    submitted_codes = {paper.paper_code.casefold() for paper in payload.papers}
    for existing in db.query(Course).all():
        if existing.id not in submitted_ids and existing.course_code.casefold() in submitted_codes:
            raise HTTPException(
                status_code=409,
                detail=f"Paper code {existing.course_code} is already used in the course catalogue.",
            )

    programme.catalogue_course_name = payload.course_name
    programme.catalogue_course_code = payload.course_code
    programme.faculty_school = payload.faculty_school
    programme.department = payload.department
    programme.course_description = payload.description
    programme.regulation_year = payload.regulation_year
    programme.effective_from = payload.effective_from
    programme.effective_until = payload.effective_until
    programme.catalogue_status = payload.status

    retained_ids = set(submitted_ids)
    for existing in current_papers:
        if existing.id not in retained_ids:
            existing.status = "archived"
    for paper in payload.papers:
        course = current_by_id.get(paper.id) if paper.id else None
        if course is None:
            course = Course(
                course_code=paper.paper_code,
                name=paper.paper_title,
                category=paper.category,
                semester=paper.semester,
                course_type=paper.paper_type,
                credits=paper.credits,
                lecture_hours=paper.lecture_hours,
                tutorial_hours=paper.tutorial_hours,
                practical_hours=paper.practical_hours,
                internal_marks=paper.internal_marks,
                external_marks=paper.external_marks,
                description="",
                objectives=[],
                prerequisites=[],
                programme_id=programme.id,
                programme_ids=[str(programme.id)],
                status=payload.status,
                created_by=admin.id,
            )
            db.add(course)
        else:
            course.course_code = paper.paper_code
            course.name = paper.paper_title
            course.category = paper.category
            course.semester = paper.semester
            course.course_type = paper.paper_type
            course.lecture_hours = paper.lecture_hours
            course.tutorial_hours = paper.tutorial_hours
            course.practical_hours = paper.practical_hours
            course.internal_marks = paper.internal_marks
            course.external_marks = paper.external_marks
            course.credits = paper.credits
            course.programme_id = programme.id
            programme_id_text = str(programme.id)
            if programme_id_text not in (course.programme_ids or []):
                course.programme_ids = [*(course.programme_ids or []), programme_id_text]
            course.status = payload.status
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A course or paper code conflicts with existing catalogue data.") from exc
    return library_detail(db, programme)


@router.delete("/library/{programme_id}", status_code=204)
def archive_course_library(
    programme_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
) -> None:
    programme = db.get(Programme, programme_id)
    if programme is None or programme.catalogue_course_code is None:
        raise HTTPException(status_code=404, detail="Course not found")
    programme.catalogue_status = "archived"
    for paper in programme_courses(db, programme, include_archived=True):
        paper.status = "archived"
    db.commit()


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
