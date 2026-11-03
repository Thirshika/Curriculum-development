import re
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.curriculum_exports import render_curriculum_docx, render_curriculum_pdf
from app.curriculum_generation import validate_curriculum
from app.dependencies import CurrentUser, DbSession, require_role
from app.models import (
    CurriculumAssignment,
    College,
    CurriculumGenerationJob,
    CurriculumLibraryItem,
    CurriculumVersion,
    Notification,
    Programme,
    University,
    User,
    UserRole,
)
from app.routers.ai_generation import response_content
from app.schemas import (
    CurriculumAssignmentResponse,
    CurriculumDraftContent,
    CurriculumLibraryCreate,
    CurriculumLibraryResponse,
    CurriculumLibraryUpdate,
    CurriculumPublishRequest,
    CurriculumVersionResponse,
    GeneratedCurriculumContent,
    NotificationReadResponse,
    NotificationResponse,
    PublishResult,
)

router = APIRouter(prefix="/api/curricula", tags=["curricula"])
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
ReviewerUser = Annotated[User, Depends(require_role(UserRole.REVIEWER))]


def library_query(db):
    return db.query(CurriculumLibraryItem).options(
        joinedload(CurriculumLibraryItem.programme).joinedload(Programme.university),
        joinedload(CurriculumLibraryItem.versions),
    )


def current_version(item: CurriculumLibraryItem) -> CurriculumVersion:
    if not item.versions:
        raise HTTPException(status_code=409, detail="Curriculum has no saved version")
    return max(item.versions, key=lambda version: version.version_number)


def version_response(version: CurriculumVersion) -> CurriculumVersionResponse:
    return CurriculumVersionResponse(
        id=version.id,
        version_number=version.version_number,
        content=version.content,
        created_at=version.created_at,
    )


def library_response(item: CurriculumLibraryItem) -> CurriculumLibraryResponse:
    programme = item.programme
    return CurriculumLibraryResponse(
        id=item.id,
        generation_job_id=item.generation_job_id,
        programme_id=programme.id,
        programme_name=programme.name,
        university_id=programme.university_id,
        university_name=programme.university.name,
        college_id=programme.college_id,
        college_name=programme.college.name if programme.college else None,
        title=item.title,
        academic_year=programme.academic_year,
        status=item.status,
        current_version_number=item.current_version_number,
        current_version=version_response(current_version(item)),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def assignment_response(assignment: CurriculumAssignment) -> CurriculumAssignmentResponse:
    item = assignment.curriculum
    return CurriculumAssignmentResponse(
        id=assignment.id,
        curriculum_id=item.id,
        version_id=assignment.version_id,
        version_number=assignment.version.version_number,
        curriculum_title=item.title,
        programme_name=item.programme.name,
        university_name=assignment.university.name,
        college_id=assignment.college_id,
        college_name=assignment.college.name if assignment.college else None,
        status=assignment.status,
        deadline=assignment.deadline,
        published_at=assignment.published_at,
    )


def load_item(db, curriculum_id: uuid.UUID) -> CurriculumLibraryItem:
    item = library_query(db).filter(CurriculumLibraryItem.id == curriculum_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return item


def export_response(
    *,
    item: CurriculumLibraryItem,
    version: CurriculumVersion,
    file_format: Literal["docx", "pdf"],
) -> Response:
    programme = item.programme
    details = {
        "title": item.title,
        "university": programme.university.name,
        "programme": programme.name,
        "academic_year": programme.academic_year,
        "version_number": version.version_number,
        "content": version.content,
    }
    if file_format == "docx":
        content = render_curriculum_docx(**details)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        suffix = "docx"
    else:
        content = render_curriculum_pdf(**details)
        media_type = "application/pdf"
        suffix = "pdf"
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", item.title).strip("-") or "curriculum"
    filename = f"{safe_title}-v{version.version_number}.{suffix}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("", response_model=list[CurriculumLibraryResponse])
def list_curricula(
    db: DbSession,
    _admin: AdminUser,
    search: str | None = Query(default=None, max_length=120),
    university_id: uuid.UUID | None = None,
    programme_id: uuid.UUID | None = None,
    curriculum_status: str | None = Query(default=None, alias="status", pattern="^(draft|published|archived)$"),
    sort_by: str = Query(default="updated_at", pattern="^(updated_at|title|university|programme)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[CurriculumLibraryResponse]:
    query = library_query(db).join(CurriculumLibraryItem.programme).join(Programme.university)
    if university_id:
        query = query.filter(Programme.university_id == university_id)
    if programme_id:
        query = query.filter(CurriculumLibraryItem.programme_id == programme_id)
    if curriculum_status:
        query = query.filter(CurriculumLibraryItem.status == curriculum_status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                CurriculumLibraryItem.title.ilike(pattern),
                Programme.name.ilike(pattern),
                Programme.academic_year.ilike(pattern),
            )
        )
    sort_columns = {
        "updated_at": CurriculumLibraryItem.updated_at,
        "title": CurriculumLibraryItem.title,
        "programme": Programme.name,
        "university": University.name,
    }
    ordering = sort_columns[sort_by]
    query = query.order_by(ordering.asc() if sort_order == "asc" else ordering.desc())
    return [library_response(item) for item in query.offset(offset).limit(limit).all()]


@router.post("", response_model=CurriculumLibraryResponse, status_code=status.HTTP_201_CREATED)
def create_library_curriculum(
    payload: CurriculumLibraryCreate,
    db: DbSession,
    admin: AdminUser,
) -> CurriculumLibraryResponse:
    job = db.get(CurriculumGenerationJob, payload.generation_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Curriculum generation job not found")
    if job.status != "completed" or not job.curriculum:
        raise HTTPException(status_code=409, detail="Only completed generation drafts can be added to the library.")
    if db.query(CurriculumLibraryItem.id).filter(
        CurriculumLibraryItem.generation_job_id == job.id
    ).first():
        raise HTTPException(status_code=409, detail="This generation draft is already in the curriculum library.")
    programme = db.query(Programme).options(joinedload(Programme.university)).filter(
        Programme.id == job.programme_id
    ).first()
    if programme is None:
        raise HTTPException(status_code=404, detail="Programme not found")

    item = CurriculumLibraryItem(
        programme_id=programme.id,
        generation_job_id=job.id,
        title=(payload.title or f"{programme.name} Curriculum").strip(),
        status="draft",
        current_version_number=1,
        created_by=admin.id,
    )
    version = CurriculumVersion(
        version_number=1,
        content=job.curriculum,
        regulatory_references=[],
        validation_status="not_run",
        validation_checks=[],
        created_by=admin.id,
    )
    item.versions.append(version)
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This generation draft is already in the curriculum library.") from exc
    item = library_query(db).filter(CurriculumLibraryItem.id == item.id).first()
    return library_response(item)


@router.get("/{curriculum_id}", response_model=CurriculumLibraryResponse)
def get_curriculum(curriculum_id: uuid.UUID, db: DbSession, _admin: AdminUser) -> CurriculumLibraryResponse:
    return library_response(load_item(db, curriculum_id))


@router.get("/{curriculum_id}/versions", response_model=list[CurriculumVersionResponse])
def list_curriculum_versions(
    curriculum_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
) -> list[CurriculumVersionResponse]:
    item = load_item(db, curriculum_id)
    return [version_response(version) for version in item.versions]


@router.patch("/{curriculum_id}", response_model=CurriculumLibraryResponse)
def update_curriculum(
    curriculum_id: uuid.UUID,
    payload: CurriculumLibraryUpdate,
    db: DbSession,
    admin: AdminUser,
) -> CurriculumLibraryResponse:
    item = load_item(db, curriculum_id)
    if item.status == "archived":
        raise HTTPException(status_code=409, detail="Archived curricula cannot be edited.")
    updates = payload.model_dump(exclude_unset=True)
    title = updates.get("title")
    if title is not None:
        item.title = title.strip()
    content = updates.get("content")
    if content is not None:
        version = current_version(item)
        generated = GeneratedCurriculumContent.model_validate(
            CurriculumDraftContent.model_validate(content).model_dump(exclude={"credit_distribution"})
        )
        try:
            validate_curriculum(generated, semester_count=item.programme.semester_count)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        updated_content = CurriculumDraftContent.model_validate(response_content(generated))
        new_version_number = item.current_version_number + 1
        item.versions.append(
            CurriculumVersion(
                version_number=new_version_number,
                content=updated_content.model_dump(mode="json"),
                regulatory_references=[],
                validation_status="not_run",
                validation_checks=[],
                created_by=admin.id,
            )
        )
        item.current_version_number = new_version_number
        if item.status == "published":
            item.status = "draft"
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="The curriculum update conflicts with another change.") from exc
    return library_response(load_item(db, curriculum_id))


@router.get("/{curriculum_id}/versions/{version_number}/export")
def export_curriculum(
    curriculum_id: uuid.UUID,
    version_number: int,
    db: DbSession,
    _admin: AdminUser,
    file_format: Literal["docx", "pdf"] = Query(alias="format"),
) -> Response:
    item = load_item(db, curriculum_id)
    version = next((item_version for item_version in item.versions if item_version.version_number == version_number), None)
    if version is None:
        raise HTTPException(status_code=404, detail="Curriculum version not found")
    return export_response(item=item, version=version, file_format=file_format)


@router.post("/{curriculum_id}/publish", response_model=PublishResult, status_code=status.HTTP_201_CREATED)
def publish_curriculum(
    curriculum_id: uuid.UUID,
    payload: CurriculumPublishRequest,
    db: DbSession,
    _admin: AdminUser,
) -> PublishResult:
    item = load_item(db, curriculum_id)
    if item.status == "archived":
        raise HTTPException(status_code=409, detail="Archived curricula cannot be published.")
    reviewer = db.query(User).filter(
        User.id == payload.reviewer_id,
        User.role == UserRole.REVIEWER,
        User.university_id == item.programme.university_id,
    ).first()
    if reviewer is None or not reviewer.is_active or reviewer.must_change_password:
        raise HTTPException(
            status_code=409,
            detail="Select an active reviewer assigned to this programme's university who has completed the first sign-in password change.",
        )
    college_id = payload.college_id or reviewer.college_id
    if item.programme.college_id and college_id != item.programme.college_id:
        raise HTTPException(status_code=403, detail="A college-owned programme can only be assigned to its owning college.")
    if reviewer.college_id is not None and payload.college_id not in {None, reviewer.college_id}:
        raise HTTPException(status_code=403, detail="A college reviewer can only receive assignments for their own college.")
    if college_id:
        college = db.query(College).filter(
            College.id == college_id,
            College.university_id == item.programme.university_id,
            College.status == "active",
        ).first()
        if college is None:
            raise HTTPException(status_code=422, detail="The selected college must be active and belong to this programme's university.")
        if reviewer.college_id != college.id:
            raise HTTPException(status_code=403, detail="Select the active reviewer assigned to this college.")
    version = current_version(item)
    assignment = CurriculumAssignment(
        curriculum_id=item.id,
        version_id=version.id,
        university_id=item.programme.university_id,
        reviewer_id=reviewer.id,
        college_id=college_id,
        deadline=payload.deadline,
        status="pending",
    )
    item.status = "published"
    db.add(assignment)
    db.flush()
    db.add(
        Notification(
            user_id=reviewer.id,
            assignment_id=assignment.id,
            title="Curriculum assigned for review",
            message=f"{item.title} (version {version.version_number}) was published by the platform administrator.",
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This curriculum version is already published to the selected reviewer.",
        ) from exc
    assignment = (
        db.query(CurriculumAssignment)
        .options(
            joinedload(CurriculumAssignment.curriculum).joinedload(CurriculumLibraryItem.programme),
            joinedload(CurriculumAssignment.version),
            joinedload(CurriculumAssignment.university),
        )
        .filter(CurriculumAssignment.id == assignment.id)
        .first()
    )
    return PublishResult(assignment=assignment_response(assignment))


@router.post("/{curriculum_id}/archive", response_model=CurriculumLibraryResponse)
def archive_curriculum(
    curriculum_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
) -> CurriculumLibraryResponse:
    item = load_item(db, curriculum_id)
    item.status = "archived"
    db.commit()
    return library_response(load_item(db, curriculum_id))


@router.get("/reviewer/assignments", response_model=list[CurriculumAssignmentResponse])
def reviewer_assignments(db: DbSession, reviewer: ReviewerUser) -> list[CurriculumAssignmentResponse]:
    assignments = (
        db.query(CurriculumAssignment)
        .options(
            joinedload(CurriculumAssignment.curriculum).joinedload(CurriculumLibraryItem.programme),
            joinedload(CurriculumAssignment.version),
            joinedload(CurriculumAssignment.university),
        )
        .filter(CurriculumAssignment.reviewer_id == reviewer.id)
        .order_by(CurriculumAssignment.published_at.desc())
        .all()
    )
    return [assignment_response(assignment) for assignment in assignments]


@router.get("/reviewer/assignments/{assignment_id}/download")
def download_reviewer_assignment(
    assignment_id: uuid.UUID,
    db: DbSession,
    reviewer: ReviewerUser,
    file_format: Literal["docx", "pdf"] = Query(alias="format"),
) -> Response:
    assignment = (
        db.query(CurriculumAssignment)
        .options(
            joinedload(CurriculumAssignment.curriculum)
            .joinedload(CurriculumLibraryItem.programme)
            .joinedload(Programme.university),
            joinedload(CurriculumAssignment.version),
        )
        .filter(
            CurriculumAssignment.id == assignment_id,
            CurriculumAssignment.reviewer_id == reviewer.id,
            CurriculumAssignment.university_id == reviewer.university_id,
        )
        .first()
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Published curriculum assignment not found")
    return export_response(item=assignment.curriculum, version=assignment.version, file_format=file_format)


@router.get("/reviewer/notifications", response_model=list[NotificationResponse])
def list_notifications(db: DbSession, user: CurrentUser) -> list[NotificationResponse]:
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )
    return notifications


@router.post("/reviewer/notifications/{notification_id}/read", response_model=NotificationReadResponse)
def mark_notification_read(
    notification_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> NotificationReadResponse:
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ).first()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return NotificationReadResponse(id=notification.id, read_at=notification.read_at)
