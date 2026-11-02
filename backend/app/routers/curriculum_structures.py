import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import joinedload

from app.dependencies import DbSession, require_role
from app.models import Course, CurriculumStructure, CurriculumStructureVersion, Programme, User, UserRole
from app.routers.programmes import validate_programme_credits
from app.schemas import (
    CreditValidationRequest,
    CurriculumStructureContent,
    CurriculumStructureCreate,
    CurriculumStructureResponse,
    CurriculumStructureUpdate,
    CurriculumStructureVersionResponse,
)

router = APIRouter(prefix="/api/curriculum-structures", tags=["curriculum-structures"])


def structure_query(db: DbSession):
    return db.query(CurriculumStructure).options(
        joinedload(CurriculumStructure.programme).joinedload(Programme.university),
        joinedload(CurriculumStructure.versions),
    )


def serialize_content(content: CurriculumStructureContent) -> dict:
    return content.model_dump(mode="json")


def structure_response(structure: CurriculumStructure) -> CurriculumStructureResponse:
    version = next((item for item in structure.versions if item.version_number == structure.current_version), None)
    if version is None:
        raise HTTPException(status_code=409, detail="Curriculum structure is missing its current version.")
    return CurriculumStructureResponse(
        id=structure.id,
        programme_id=structure.programme_id,
        programme_name=structure.programme.name,
        university_name=structure.programme.university.name,
        title=structure.title,
        current_version=structure.current_version,
        version=CurriculumStructureVersionResponse(
            id=version.id,
            version_number=version.version_number,
            content=CurriculumStructureContent.model_validate(version.content),
            validation=version.validation,
            created_at=version.created_at,
        ),
        created_at=structure.created_at,
        updated_at=structure.updated_at,
    )


def validate_course_references(db: DbSession, content: CurriculumStructureContent) -> None:
    ids = {course.course_id for semester in content.semesters for course in semester.courses}
    if not ids:
        raise HTTPException(status_code=422, detail="Add at least one course to the curriculum structure.")
    found = {row[0] for row in db.query(Course.id).filter(Course.id.in_(ids), Course.status == "active").all()}
    if found != ids:
        raise HTTPException(status_code=422, detail="Every structure course must exist and be active in the course library.")


@router.get("", response_model=list[CurriculumStructureResponse])
def list_structures(
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
    programme_id: uuid.UUID | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[CurriculumStructureResponse]:
    query = structure_query(db)
    if programme_id:
        query = query.filter(CurriculumStructure.programme_id == programme_id)
    return [structure_response(item) for item in query.order_by(CurriculumStructure.updated_at.desc()).offset(offset).limit(limit).all()]


@router.post("", response_model=CurriculumStructureResponse, status_code=status.HTTP_201_CREATED)
def create_structure(
    payload: CurriculumStructureCreate,
    db: DbSession,
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CurriculumStructureResponse:
    programme = db.get(Programme, payload.programme_id)
    if programme is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    if len(payload.content.semesters) != programme.semester_count:
        raise HTTPException(status_code=422, detail=f"Structure must contain exactly {programme.semester_count} semesters.")
    if [semester.semester_number for semester in payload.content.semesters] != list(range(1, programme.semester_count + 1)):
        raise HTTPException(status_code=422, detail="Semesters must be numbered consecutively from 1.")
    validate_course_references(db, payload.content)
    structure = CurriculumStructure(
        programme_id=programme.id,
        title=payload.title.strip(),
        current_version=1,
        created_by=admin.id,
    )
    structure.versions.append(CurriculumStructureVersion(
        version_number=1,
        content=serialize_content(payload.content),
        created_by=admin.id,
    ))
    db.add(structure)
    db.commit()
    return structure_response(structure_query(db).filter(CurriculumStructure.id == structure.id).one())


@router.get("/{structure_id}", response_model=CurriculumStructureResponse)
def get_structure(
    structure_id: uuid.UUID,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CurriculumStructureResponse:
    structure = structure_query(db).filter(CurriculumStructure.id == structure_id).first()
    if structure is None:
        raise HTTPException(status_code=404, detail="Curriculum structure not found")
    return structure_response(structure)


@router.patch("/{structure_id}", response_model=CurriculumStructureResponse)
def update_structure(
    structure_id: uuid.UUID,
    payload: CurriculumStructureUpdate,
    db: DbSession,
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CurriculumStructureResponse:
    structure = structure_query(db).filter(CurriculumStructure.id == structure_id).first()
    if structure is None:
        raise HTTPException(status_code=404, detail="Curriculum structure not found")
    updates = payload.model_dump(exclude_unset=True)
    content = updates.get("content")
    if content is not None:
        content = CurriculumStructureContent.model_validate(content)
        if len(content.semesters) != structure.programme.semester_count:
            raise HTTPException(status_code=422, detail=f"Structure must contain exactly {structure.programme.semester_count} semesters.")
        if [semester.semester_number for semester in content.semesters] != list(range(1, structure.programme.semester_count + 1)):
            raise HTTPException(status_code=422, detail="Semesters must be numbered consecutively from 1.")
        validate_course_references(db, content)
        next_version = structure.current_version + 1
        structure.versions.append(CurriculumStructureVersion(
            version_number=next_version,
            content=serialize_content(content),
            created_by=admin.id,
        ))
        structure.current_version = next_version
    title = updates.get("title")
    if title is not None:
        structure.title = title.strip()
    db.commit()
    return structure_response(structure_query(db).filter(CurriculumStructure.id == structure.id).one())


@router.post("/{structure_id}/validate", response_model=CurriculumStructureResponse)
def validate_structure(
    structure_id: uuid.UUID,
    db: DbSession,
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CurriculumStructureResponse:
    structure = structure_query(db).filter(CurriculumStructure.id == structure_id).first()
    if structure is None:
        raise HTTPException(status_code=404, detail="Curriculum structure not found")
    version = next(item for item in structure.versions if item.version_number == structure.current_version)
    content = CurriculumStructureContent.model_validate(version.content)
    if len(content.semesters) != structure.programme.semester_count:
        raise HTTPException(status_code=422, detail="Structure semester count no longer matches the programme.")
    credits = [sum((course.credits for course in semester.courses), start=0) for semester in content.semesters]
    result = validate_programme_credits(
        structure.programme_id,
        CreditValidationRequest(semester_credits=credits),
        db,
        admin,
    )
    course_ids = {course.course_id for semester in content.semesters for course in semester.courses}
    courses = db.query(Course).filter(Course.id.in_(course_ids)).all()
    categories = {}
    for course in courses:
        categories[course.category] = categories.get(course.category, 0) + 1
    missing_major = not any(name.lower() in {"major", "core"} for name in categories)
    validation = result.model_dump(mode="json")
    validation["category_distribution"] = categories
    validation["warnings"] = ["No Major/Core course is included in this structure."] if missing_major else []
    version.validation = validation
    db.commit()
    return structure_response(structure_query(db).filter(CurriculumStructure.id == structure.id).one())
