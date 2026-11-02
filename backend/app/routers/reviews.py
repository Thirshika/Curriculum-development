import hashlib
import uuid
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import pymupdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.config import settings
from app.dependencies import CurrentUser, DbSession, require_role
from app.models import (
    CommentReply,
    CurriculumAssignment,
    CurriculumLibraryItem,
    CurriculumVersion,
    Notification,
    Programme,
    ReviewComment,
    ReviewDocument,
    ReviewHistory,
    User,
    UserRole,
)
from app.schemas import (
    CommentReplyResponse,
    CurriculumVersionComparisonResponse,
    FinalApprovalRequest,
    FinalApprovalResponse,
    ReviewCommentCreate,
    ReviewCommentReplyCreate,
    ReviewCommentResponse,
    ReviewCommentStatusUpdate,
    ReviewCommentUpdate,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewDocumentResponse,
    ReviewHistoryResponse,
    ReviewerReviewResponse,
)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def assignment_query(db: DbSession):
    return db.query(CurriculumAssignment).options(
        joinedload(CurriculumAssignment.curriculum)
        .joinedload(CurriculumLibraryItem.programme)
        .joinedload(Programme.university),
        joinedload(CurriculumAssignment.version),
        joinedload(CurriculumAssignment.university),
        joinedload(CurriculumAssignment.reviewer),
    )


def get_assignment(db: DbSession, assignment_id: uuid.UUID, user: User) -> CurriculumAssignment:
    query = assignment_query(db).filter(CurriculumAssignment.id == assignment_id)
    if user.role == UserRole.REVIEWER:
        query = query.filter(
            CurriculumAssignment.reviewer_id == user.id,
            CurriculumAssignment.university_id == user.university_id,
        )
    assignment = query.first()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Review assignment not found")
    return assignment


def add_history(
    db: DbSession,
    assignment: CurriculumAssignment,
    user: User,
    action: str,
    details: dict | None = None,
) -> None:
    db.add(
        ReviewHistory(
            assignment_id=assignment.id,
            version_id=assignment.version_id,
            actor_id=user.id,
            action=action,
            details=details or {},
        )
    )


def notify_user(db: DbSession, user_id: uuid.UUID, assignment: CurriculumAssignment, title: str, message: str) -> None:
    db.add(
        Notification(
            user_id=user_id,
            assignment_id=assignment.id,
            title=title,
            message=message,
        )
    )


def notify_admins(db: DbSession, assignment: CurriculumAssignment, title: str, message: str) -> None:
    admin_ids = db.query(User.id).filter(User.role == UserRole.ADMIN, User.is_active.is_(True)).all()
    for (admin_id,) in admin_ids:
        notify_user(db, admin_id, assignment, title, message)


def comment_response(comment: ReviewComment) -> ReviewCommentResponse:
    return ReviewCommentResponse(
        id=comment.id,
        assignment_id=comment.assignment_id,
        version_id=comment.version_id,
        version_number=comment.version.version_number,
        section_path=comment.section_path,
        priority=comment.priority,
        body=comment.body,
        status=comment.status,
        is_submitted=comment.is_submitted,
        author_id=comment.created_by,
        author_name=comment.author.full_name,
        created_at=comment.created_at,
        submitted_at=comment.submitted_at,
        replies=[
            CommentReplyResponse(
                id=reply.id,
                author_id=reply.author_id,
                author_name=reply.author.full_name,
                author_role=reply.author.role.value,
                body=reply.body,
                created_at=reply.created_at,
            )
            for reply in comment.replies
        ],
    )


def document_response(document: ReviewDocument) -> ReviewDocumentResponse:
    return ReviewDocumentResponse(
        id=document.id,
        assignment_id=document.assignment_id,
        version_id=document.version_id,
        related_comment_id=document.related_comment_id,
        uploaded_by=document.uploaded_by,
        uploader_name=document.uploader.full_name,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size=document.file_size,
        created_at=document.created_at,
    )


def assignment_response(assignment: CurriculumAssignment) -> dict:
    return {
        "id": assignment.id,
        "curriculum_id": assignment.curriculum_id,
        "version_id": assignment.version_id,
        "version_number": assignment.version.version_number,
        "curriculum_title": assignment.curriculum.title,
        "programme_name": assignment.curriculum.programme.name,
        "university_name": assignment.university.name,
        "status": assignment.status,
        "deadline": assignment.deadline,
        "published_at": assignment.published_at,
        "validation_status": assignment.version.validation_status,
    }


def history_response(history: ReviewHistory) -> ReviewHistoryResponse:
    return ReviewHistoryResponse(
        id=history.id,
        version_id=history.version_id,
        version_number=history.version.version_number,
        actor_id=history.actor_id,
        actor_name=history.actor.full_name,
        action=history.action,
        details=history.details,
        created_at=history.created_at,
    )


def validate_review_file(filename: str, data: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        try:
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                if pdf.page_count < 1:
                    raise ValueError("PDF contains no pages")
        except (pymupdf.FileDataError, pymupdf.EmptyFileError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="The uploaded PDF is invalid or unreadable.") from exc
        return "application/pdf"
    if extension == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                entries = {item.filename: item for item in archive.infolist()}
                if "[Content_Types].xml" not in entries or "word/document.xml" not in entries:
                    raise ValueError("Missing DOCX document parts")
                if sum(item.file_size for item in entries.values()) > 100 * 1024 * 1024:
                    raise ValueError("DOCX expands beyond the allowed size")
                if any(item.file_size > max(item.compress_size, 1) * 100 for item in entries.values()):
                    raise ValueError("DOCX contains an excessive compression ratio")
        except (zipfile.BadZipFile, ValueError) as exc:
            raise HTTPException(status_code=422, detail="The uploaded Word document is invalid or unreadable.") from exc
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    raise HTTPException(status_code=415, detail="Only PDF and DOCX review documents are accepted.")


def build_review_response(db: DbSession, assignment: CurriculumAssignment, include_drafts: bool) -> ReviewerReviewResponse:
    comments_query = db.query(ReviewComment).options(
        joinedload(ReviewComment.version),
        joinedload(ReviewComment.author),
        joinedload(ReviewComment.replies).joinedload(CommentReply.author),
    ).filter(ReviewComment.assignment_id == assignment.id)
    if not include_drafts:
        comments_query = comments_query.filter(ReviewComment.is_submitted.is_(True))
    comments = comments_query.order_by(ReviewComment.created_at.asc()).all()
    documents = db.query(ReviewDocument).options(joinedload(ReviewDocument.uploader)).filter(
        ReviewDocument.assignment_id == assignment.id
    ).order_by(ReviewDocument.created_at.desc()).all()
    history = db.query(ReviewHistory).options(
        joinedload(ReviewHistory.version),
        joinedload(ReviewHistory.actor),
    ).filter(ReviewHistory.assignment_id == assignment.id).order_by(ReviewHistory.created_at.desc()).all()
    return ReviewerReviewResponse(
        assignment=assignment_response(assignment),
        curriculum_content=assignment.version.content,
        regulatory_references=assignment.version.regulatory_references,
        validation_checks=assignment.version.validation_checks,
        comments=[comment_response(comment) for comment in comments],
        documents=[document_response(document) for document in documents],
        history=[history_response(event) for event in history],
    )


@router.get("/assignments")
def list_review_assignments(
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
    assignment_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|under_review|revision_requested|reviewer_recommended|reviewer_rejected|approved|rejected)$",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[ReviewerReviewResponse]:
    query = assignment_query(db)
    if assignment_status:
        query = query.filter(CurriculumAssignment.status == assignment_status)
    assignments = query.order_by(CurriculumAssignment.published_at.desc()).offset(offset).limit(limit).all()
    return [build_review_response(db, item, include_drafts=False) for item in assignments]


@router.get("/assignments/{assignment_id}", response_model=ReviewerReviewResponse)
def get_review_assignment(
    assignment_id: uuid.UUID,
    db: DbSession,
    reviewer: User = Depends(require_role(UserRole.REVIEWER)),
) -> ReviewerReviewResponse:
    assignment = get_assignment(db, assignment_id, reviewer)
    if assignment.status == "pending":
        assignment.status = "under_review"
        add_history(db, assignment, reviewer, "review_opened")
        db.commit()
    return build_review_response(
        db,
        assignment,
        include_drafts=assignment.status in {"pending", "under_review"},
    )


@router.post(
    "/assignments/{assignment_id}/comments",
    response_model=ReviewCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review_comment(
    assignment_id: uuid.UUID,
    payload: ReviewCommentCreate,
    db: DbSession,
    reviewer: User = Depends(require_role(UserRole.REVIEWER)),
) -> ReviewCommentResponse:
    assignment = get_assignment(db, assignment_id, reviewer)
    if assignment.status not in {"pending", "under_review"}:
        raise HTTPException(status_code=409, detail="Comments cannot be added to a completed review.")
    if assignment.status == "pending":
        assignment.status = "under_review"
    now = datetime.now(timezone.utc)
    comment = ReviewComment(
        assignment_id=assignment.id,
        version_id=assignment.version_id,
        section_path=payload.section_path or None,
        priority=payload.priority,
        body=payload.body,
        status="open",
        is_submitted=payload.is_submitted,
        created_by=reviewer.id,
        submitted_at=now if payload.is_submitted else None,
    )
    db.add(comment)
    add_history(
        db,
        assignment,
        reviewer,
        "comment_submitted" if payload.is_submitted else "comment_drafted",
        {"section_path": payload.section_path, "priority": payload.priority},
    )
    if payload.is_submitted:
        notify_admins(
            db,
            assignment,
            "Reviewer submitted feedback",
            f"{reviewer.full_name} submitted a {payload.priority}-priority comment on {assignment.curriculum.title}.",
        )
    db.commit()
    comment = db.query(ReviewComment).options(
        joinedload(ReviewComment.version),
        joinedload(ReviewComment.author),
        joinedload(ReviewComment.replies).joinedload(CommentReply.author),
    ).filter(ReviewComment.id == comment.id).one()
    return comment_response(comment)


@router.patch("/comments/{comment_id}", response_model=ReviewCommentResponse)
def update_review_comment(
    comment_id: uuid.UUID,
    payload: ReviewCommentUpdate,
    db: DbSession,
    reviewer: User = Depends(require_role(UserRole.REVIEWER)),
) -> ReviewCommentResponse:
    comment = (
        db.query(ReviewComment)
        .join(CurriculumAssignment)
        .filter(
            ReviewComment.id == comment_id,
            ReviewComment.created_by == reviewer.id,
            ReviewComment.is_submitted.is_(False),
            CurriculumAssignment.reviewer_id == reviewer.id,
            CurriculumAssignment.university_id == reviewer.university_id,
        )
        .first()
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="Review draft not found")
    assignment = get_assignment(db, comment.assignment_id, reviewer)
    if assignment.status not in {"pending", "under_review"}:
        raise HTTPException(status_code=409, detail="This assignment is no longer accepting review changes.")
    updates = payload.model_dump(exclude_unset=True)
    for field in ("body", "section_path", "priority"):
        if field in updates:
            setattr(comment, field, updates[field])
    if "is_submitted" in updates:
        comment.is_submitted = updates["is_submitted"]
    if comment.is_submitted and comment.submitted_at is None:
        comment.submitted_at = datetime.now(timezone.utc)
    add_history(
        db,
        assignment,
        reviewer,
        "comment_submitted" if comment.is_submitted else "comment_drafted",
        {"comment_id": str(comment.id), "section_path": comment.section_path, "priority": comment.priority},
    )
    if comment.is_submitted:
        notify_admins(
            db,
            assignment,
            "Reviewer submitted feedback",
            f"{reviewer.full_name} submitted a {comment.priority}-priority comment on {assignment.curriculum.title}.",
        )
    db.commit()
    comment = db.query(ReviewComment).options(
        joinedload(ReviewComment.version),
        joinedload(ReviewComment.author),
        joinedload(ReviewComment.replies).joinedload(CommentReply.author),
    ).filter(ReviewComment.id == comment.id).one()
    return comment_response(comment)


@router.post("/assignments/{assignment_id}/submit", response_model=ReviewDecisionResponse)
def submit_review_decision(
    assignment_id: uuid.UUID,
    payload: ReviewDecisionRequest,
    db: DbSession,
    reviewer: User = Depends(require_role(UserRole.REVIEWER)),
) -> ReviewDecisionResponse:
    assignment = get_assignment(db, assignment_id, reviewer)
    if assignment.status not in {"pending", "under_review"}:
        raise HTTPException(status_code=409, detail="This review has already been submitted.")
    drafts = db.query(ReviewComment.id).filter(
        ReviewComment.assignment_id == assignment.id,
        ReviewComment.is_submitted.is_(False),
    ).count()
    if drafts:
        raise HTTPException(status_code=409, detail="Submit or remove all draft comments before completing the review.")
    submitted_comments = db.query(ReviewComment).filter(
        ReviewComment.assignment_id == assignment.id,
        ReviewComment.is_submitted.is_(True),
    ).all()
    if payload.decision == "revision_requested" and not submitted_comments:
        raise HTTPException(status_code=422, detail="Submit at least one comment before requesting revisions.")
    if payload.decision == "reviewer_recommended" and any(comment.status != "resolved" for comment in submitted_comments):
        raise HTTPException(status_code=409, detail="Resolve all submitted comments before approving this curriculum.")

    assignment.status = payload.decision
    add_history(
        db,
        assignment,
        reviewer,
        payload.decision,
        {"message": payload.message} if payload.message else {},
    )
    notify_admins(
        db,
        assignment,
        "Curriculum review completed",
        f"{reviewer.full_name} {payload.decision.replace('_', ' ')} {assignment.curriculum.title} (version {assignment.version.version_number}).",
    )
    db.commit()
    return ReviewDecisionResponse(
        assignment=assignment_response(assignment),
        decision=payload.decision,
        message=payload.message,
    )


@router.post("/admin/assignments/{assignment_id}/final-decision", response_model=FinalApprovalResponse)
def set_final_approval(
    assignment_id: uuid.UUID,
    payload: FinalApprovalRequest,
    db: DbSession,
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> FinalApprovalResponse:
    assignment = get_assignment(db, assignment_id, admin)
    if assignment.status not in {"reviewer_recommended", "reviewer_rejected", "revision_requested"}:
        raise HTTPException(
            status_code=409,
            detail="Final approval or rejection requires a submitted reviewer recommendation, rejection, or revision request.",
        )
    if payload.decision == "approved":
        unresolved = db.query(ReviewComment.id).filter(
            ReviewComment.assignment_id == assignment.id,
            ReviewComment.is_submitted.is_(True),
            ReviewComment.status != "resolved",
        ).first()
        if unresolved is not None:
            raise HTTPException(status_code=409, detail="Resolve all submitted reviewer comments before final approval.")

    previous_status = assignment.status
    assignment.status = payload.decision
    add_history(
        db,
        assignment,
        admin,
        "final_approved" if payload.decision == "approved" else "final_rejected",
        {"previous_status": previous_status, "reason": payload.reason},
    )
    notify_user(
        db,
        assignment.reviewer_id,
        assignment,
        "Final curriculum decision recorded",
        (
            f"The platform administrator gave final approval to {assignment.curriculum.title} "
            f"(version {assignment.version.version_number})."
            if payload.decision == "approved"
            else f"The platform administrator rejected {assignment.curriculum.title}: {payload.reason}"
        ),
    )
    db.commit()
    return FinalApprovalResponse(
        assignment=assignment_response(assignment),
        decision=payload.decision,
        reason=payload.reason,
    )


@router.post("/assignments/{assignment_id}/documents", response_model=ReviewDocumentResponse, status_code=201)
async def upload_review_document(
    assignment_id: uuid.UUID,
    db: DbSession,
    reviewer: User = Depends(require_role(UserRole.REVIEWER)),
    file: UploadFile = File(...),
    related_comment_id: uuid.UUID | None = Form(default=None),
) -> ReviewDocumentResponse:
    assignment = get_assignment(db, assignment_id, reviewer)
    if assignment.status not in {"pending", "under_review"}:
        raise HTTPException(status_code=409, detail="Documents cannot be uploaded to a completed review.")
    filename = (file.filename or "").replace("\\", "/").split("/")[-1].strip()
    if not filename or len(filename) > 255 or any(ord(char) < 32 for char in filename):
        raise HTTPException(status_code=422, detail="Provide a valid document filename.")
    extension = Path(filename).suffix.lower()
    data = await file.read(settings.review_max_upload_bytes + 1)
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded document is empty.")
    if len(data) > settings.review_max_upload_bytes:
        raise HTTPException(status_code=413, detail="The uploaded document exceeds the configured size limit.")
    if related_comment_id:
        comment = db.query(ReviewComment).filter(
            ReviewComment.id == related_comment_id,
            ReviewComment.assignment_id == assignment.id,
            ReviewComment.created_by == reviewer.id,
        ).first()
        if comment is None:
            raise HTTPException(status_code=404, detail="Related review comment not found.")
    else:
        comment = None

    mime_type = validate_review_file(filename, data)
    extension = Path(filename).suffix.lower()
    storage_key = f"{uuid.uuid4().hex}{extension}"
    storage_dir = settings.review_storage_dir.resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / storage_key
    try:
        storage_path.write_bytes(data)
        document = ReviewDocument(
            assignment_id=assignment.id,
            version_id=assignment.version_id,
            related_comment_id=comment.id if comment else None,
            uploaded_by=reviewer.id,
            original_filename=filename,
            storage_key=storage_key,
            mime_type=mime_type,
            file_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
        db.add(document)
        add_history(
            db,
            assignment,
            reviewer,
            "document_uploaded",
            {"filename": filename, "related_comment_id": str(comment.id) if comment else None},
        )
        notify_admins(
            db,
            assignment,
            "Reviewer uploaded a document",
            f"{reviewer.full_name} uploaded {filename} for {assignment.curriculum.title}.",
        )
        db.commit()
    except (SQLAlchemyError, OSError):
        db.rollback()
        storage_path.unlink(missing_ok=True)
        raise
    document = db.query(ReviewDocument).options(joinedload(ReviewDocument.uploader)).filter(
        ReviewDocument.id == document.id
    ).one()
    return document_response(document)


@router.post("/admin/assignments/{assignment_id}/documents", response_model=ReviewDocumentResponse, status_code=201)
async def upload_admin_review_document(
    assignment_id: uuid.UUID,
    db: DbSession,
    admin: User = Depends(require_role(UserRole.ADMIN)),
    file: UploadFile = File(...),
) -> ReviewDocumentResponse:
    assignment = get_assignment(db, assignment_id, admin)
    if assignment.status not in {"pending", "under_review"}:
        raise HTTPException(status_code=409, detail="Files can only be attached to an active review assignment.")
    if assignment.version_id != assignment.curriculum.versions[-1].id:
        raise HTTPException(status_code=409, detail="Publish the current curriculum version before attaching its files.")
    filename = (file.filename or "").replace("\\", "/").split("/")[-1].strip()
    if not filename or len(filename) > 255 or any(ord(char) < 32 for char in filename):
        raise HTTPException(status_code=422, detail="Provide a valid document filename.")
    data = await file.read(settings.review_max_upload_bytes + 1)
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded document is empty.")
    if len(data) > settings.review_max_upload_bytes:
        raise HTTPException(status_code=413, detail="The uploaded document exceeds the configured size limit.")
    mime_type = validate_review_file(filename, data)
    storage_key = f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
    storage_dir = settings.review_storage_dir.resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / storage_key
    reviewer = assignment.reviewer
    if not reviewer.is_active:
        raise HTTPException(status_code=409, detail="The assigned reviewer account is inactive.")
    try:
        storage_path.write_bytes(data)
        document = ReviewDocument(
            assignment_id=assignment.id,
            version_id=assignment.version_id,
            uploaded_by=admin.id,
            original_filename=filename,
            storage_key=storage_key,
            mime_type=mime_type,
            file_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
        db.add(document)
        add_history(
            db,
            assignment,
            admin,
            "admin_document_uploaded",
            {"filename": filename},
        )
        notify_user(
            db,
            reviewer.id,
            assignment,
            "Administrator uploaded a revised document",
            f"{filename} was added to {assignment.curriculum.title} (version {assignment.version.version_number}).",
        )
        db.commit()
    except (SQLAlchemyError, OSError):
        db.rollback()
        storage_path.unlink(missing_ok=True)
        raise
    document = db.query(ReviewDocument).options(joinedload(ReviewDocument.uploader)).filter(
        ReviewDocument.id == document.id
    ).one()
    return document_response(document)


@router.get("/documents/{document_id}/download")
def download_review_document(
    document_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> FileResponse:
    if user.must_change_password:
        raise HTTPException(status_code=403, detail="Change your temporary password before continuing")
    query = db.query(ReviewDocument).join(CurriculumAssignment).filter(ReviewDocument.id == document_id)
    if user.role == UserRole.REVIEWER:
        query = query.filter(
            CurriculumAssignment.reviewer_id == user.id,
            CurriculumAssignment.university_id == user.university_id,
        )
    document = query.first()
    if document is None:
        raise HTTPException(status_code=404, detail="Review document not found")
    path = settings.review_storage_dir.resolve() / document.storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored review document is unavailable")
    encoded_filename = quote(document.original_filename)
    return FileResponse(
        path,
        media_type=document.mime_type,
        filename=document.original_filename,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )


@router.post("/comments/{comment_id}/replies", response_model=CommentReplyResponse, status_code=201)
def reply_to_comment(
    comment_id: uuid.UUID,
    payload: ReviewCommentReplyCreate,
    db: DbSession,
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> CommentReplyResponse:
    comment = db.query(ReviewComment).options(
        joinedload(ReviewComment.assignment).joinedload(CurriculumAssignment.curriculum),
    ).filter(
        ReviewComment.id == comment_id,
        ReviewComment.is_submitted.is_(True),
    ).first()
    if comment is None:
        raise HTTPException(status_code=404, detail="Submitted review comment not found")
    reply = CommentReply(comment_id=comment.id, author_id=admin.id, body=payload.body)
    db.add(reply)
    if comment.status in {"open", "reopened"}:
        comment.status = "admin_responded"
    assignment = comment.assignment
    reviewer = db.get(User, assignment.reviewer_id)
    if reviewer is None:
        raise HTTPException(status_code=409, detail="The assigned reviewer account is unavailable.")
    notify_user(
        db,
        reviewer.id,
        assignment,
        "Administrator replied to feedback",
        f"A response was added to your comment on {assignment.curriculum.title}.",
    )
    add_history(db, assignment, admin, "comment_replied", {"comment_id": str(comment.id)})
    db.commit()
    db.refresh(reply)
    return CommentReplyResponse(
        id=reply.id,
        author_id=admin.id,
        author_name=admin.full_name,
        author_role=admin.role.value,
        body=reply.body,
        created_at=reply.created_at,
    )


@router.patch("/comments/{comment_id}/status", response_model=ReviewCommentResponse)
def update_comment_status(
    comment_id: uuid.UUID,
    payload: ReviewCommentStatusUpdate,
    db: DbSession,
    admin: User = Depends(require_role(UserRole.ADMIN)),
) -> ReviewCommentResponse:
    comment = db.query(ReviewComment).options(
        joinedload(ReviewComment.version),
        joinedload(ReviewComment.author),
        joinedload(ReviewComment.replies).joinedload(CommentReply.author),
        joinedload(ReviewComment.assignment).joinedload(CurriculumAssignment.curriculum),
    ).filter(
        ReviewComment.id == comment_id,
        ReviewComment.is_submitted.is_(True),
    ).first()
    if comment is None:
        raise HTTPException(status_code=404, detail="Submitted review comment not found")
    if payload.status == "reopened" and comment.status != "resolved":
        raise HTTPException(status_code=409, detail="Only resolved comments can be reopened.")
    if payload.status == "resolved" and comment.status == "resolved":
        return comment_response(comment)
    previous_status = comment.status
    comment.status = payload.status
    assignment = comment.assignment
    notify_user(
        db,
        assignment.reviewer_id,
        assignment,
        "Review comment status updated",
        f"Your comment on {assignment.curriculum.title} was marked {payload.status}.",
    )
    add_history(
        db,
        assignment,
        admin,
        "comment_status_changed",
        {"comment_id": str(comment.id), "from": previous_status, "to": payload.status},
    )
    db.commit()
    db.refresh(comment)
    return comment_response(comment)


def flatten_content(value: object, path: str = "") -> dict[str, str]:
    if isinstance(value, dict):
        flattened: dict[str, str] = {}
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            flattened.update(flatten_content(child, child_path))
        return flattened
    if isinstance(value, list):
        flattened = {}
        for index, child in enumerate(value):
            flattened.update(flatten_content(child, f"{path}[{index}]"))
        return flattened
    return {path: str(value)}


@router.get("/curricula/{curriculum_id}/compare", response_model=CurriculumVersionComparisonResponse)
def compare_curriculum_versions(
    curriculum_id: uuid.UUID,
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
    from_version: int = Query(ge=1),
    to_version: int = Query(ge=1),
) -> CurriculumVersionComparisonResponse:
    curriculum = db.query(CurriculumLibraryItem).filter(CurriculumLibraryItem.id == curriculum_id).first()
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    versions = {
        version.version_number: version
        for version in db.query(CurriculumVersion).filter(
            CurriculumVersion.curriculum_id == curriculum.id,
            CurriculumVersion.version_number.in_([from_version, to_version]),
        ).all()
    }
    if from_version not in versions or to_version not in versions:
        raise HTTPException(status_code=404, detail="One or both curriculum versions were not found")
    old_content = flatten_content(versions[from_version].content)
    new_content = flatten_content(versions[to_version].content)
    changes = [
        {
            "path": path,
            "before": old_content.get(path, "(not present)"),
            "after": new_content.get(path, "(not present)"),
        }
        for path in sorted(old_content.keys() | new_content.keys())
        if old_content.get(path) != new_content.get(path)
    ]
    return CurriculumVersionComparisonResponse(
        curriculum_id=curriculum.id,
        from_version=from_version,
        to_version=to_version,
        changes=changes[:500],
    )
