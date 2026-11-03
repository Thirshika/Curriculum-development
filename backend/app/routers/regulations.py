import hashlib
import uuid
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, load_only

from app.config import settings
from app.dependencies import DbSession, require_role
from app.models import Course, RegulatoryCategory, RegulatoryDocument, RegulatoryDocumentStatus, RegulatoryRule, RuleVerificationStatus, User, UserRole
from app.regulatory import extract_credit_rules, extract_credit_table_rules, extract_courses_from_pdf, extract_pdf_pages
from app.schemas import RegulatoryDocumentResponse, RegulatoryRuleDecision, RegulatoryRuleResponse, RegulatoryRuleUpdate

router = APIRouter(tags=["regulatory-knowledge"])
AdminUser = require_role(UserRole.ADMIN)
rules_router = APIRouter(prefix="/api/regulatory-rules", tags=["regulatory-rules"])


def _is_credit_limit_rule(rule: RegulatoryRule) -> bool:
    if rule.value is None:
        return False
    if rule.rule_type in {"category_min", "category_max", "category_total"}:
        return bool(rule.category)
    if rule.rule_type in {"semester_min", "semester_max", "semester_total"}:
        return rule.semester is not None
    return rule.rule_type in {"total_min", "total_max"}


def document_response(
    document: RegulatoryDocument,
    *,
    rule_count: int | None = None,
    courses_imported: int = 0,
) -> RegulatoryDocumentResponse:
    return RegulatoryDocumentResponse(
        id=document.id,
        title=document.title,
        issuing_authority=document.issuing_authority,
        year=document.year,
        version=document.version,
        programme_level=document.programme_level,
        applies_to_all_levels=document.applicability.casefold() == "all applicable programmes",
        original_filename=document.original_filename,
        page_count=document.page_count,
        status=document.status.value,
        created_at=document.created_at,
        rule_count=rule_count if rule_count is not None else len(document.rules),
        courses_imported=courses_imported,
    )


def rule_response(rule: RegulatoryRule) -> RegulatoryRuleResponse:
    document = rule.document
    status = (
        "ignored"
        if rule.verification_status == RuleVerificationStatus.REJECTED
        else "applied"
        if (
            _is_credit_limit_rule(rule)
            and (document.programme_level or document.applicability.casefold() == "all applicable programmes")
            and document.status == RegulatoryDocumentStatus.READY
        )
        else "informational"
    )
    return RegulatoryRuleResponse(
        id=rule.id,
        document_id=document.id,
        document_title=document.title,
        issuing_authority=document.issuing_authority,
        year=document.year,
        version=document.version,
        programme_level=document.programme_level,
        clause=rule.clause,
        page_number=rule.page_number,
        text=rule.text,
        rule_type=rule.rule_type,
        category=rule.category,
        semester=rule.semester,
        value=rule.value,
        status=status,
        verified_at=rule.verified_at,
    )


def _rule_load_options():
    return (
        load_only(
            RegulatoryRule.id,
            RegulatoryRule.document_id,
            RegulatoryRule.clause,
            RegulatoryRule.page_number,
            RegulatoryRule.text,
            RegulatoryRule.rule_type,
            RegulatoryRule.category,
            RegulatoryRule.semester,
            RegulatoryRule.value,
            RegulatoryRule.verification_status,
            RegulatoryRule.verified_at,
            RegulatoryRule.has_conflict,
        ),
        joinedload(RegulatoryRule.document).load_only(
            RegulatoryDocument.id,
            RegulatoryDocument.title,
            RegulatoryDocument.issuing_authority,
            RegulatoryDocument.year,
            RegulatoryDocument.version,
            RegulatoryDocument.programme_level,
            RegulatoryDocument.status,
            RegulatoryDocument.applicability,
        ),
    )


@router.get("/api/regulations", response_model=list[RegulatoryDocumentResponse])
def list_regulatory_documents(
    db: DbSession,
    _admin: User = Depends(AdminUser),
    search: str | None = Query(default=None, max_length=120),
    issuing_authority: str | None = Query(default=None, max_length=200),
    year: int | None = Query(default=None, ge=1900, le=2200),
    programme_level: str | None = Query(default=None, pattern="^(ug|pg)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[RegulatoryDocumentResponse]:
    rule_count = (
        db.query(func.count(RegulatoryRule.id))
        .filter(RegulatoryRule.document_id == RegulatoryDocument.id)
        .correlate(RegulatoryDocument)
        .scalar_subquery()
    )
    query = db.query(RegulatoryDocument, rule_count.label("rule_count")).options(
        load_only(
            RegulatoryDocument.id,
            RegulatoryDocument.title,
            RegulatoryDocument.issuing_authority,
            RegulatoryDocument.year,
            RegulatoryDocument.version,
            RegulatoryDocument.programme_level,
            RegulatoryDocument.original_filename,
            RegulatoryDocument.page_count,
            RegulatoryDocument.status,
            RegulatoryDocument.created_at,
        )
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(RegulatoryDocument.title.ilike(pattern), RegulatoryDocument.issuing_authority.ilike(pattern)))
    if issuing_authority:
        query = query.filter(RegulatoryDocument.issuing_authority.ilike(f"%{issuing_authority.strip()}%"))
    if year is not None:
        query = query.filter(RegulatoryDocument.year == year)
    if programme_level:
        query = query.filter(RegulatoryDocument.programme_level == programme_level)
    documents = query.order_by(RegulatoryDocument.created_at.desc()).offset(offset).limit(limit).all()
    return [
        document_response(document, rule_count=count)
        for document, count in documents
    ]


@router.post("/api/regulations", response_model=RegulatoryDocumentResponse, status_code=201)
async def upload_regulatory_document(
    db: DbSession,
    admin: User = Depends(AdminUser),
    title: str = Form(min_length=2, max_length=240),
    issuing_authority: str = Form(min_length=2, max_length=200),
    year: int = Form(ge=1900, le=2200),
    version: str = Form(min_length=1, max_length=80),
    programme_level: str = Form(pattern="^(ug|pg)$"),
    file: UploadFile = File(...),
) -> RegulatoryDocumentResponse:
    if not file.filename or file.filename.rsplit(".", 1)[-1].lower() != "pdf":
        raise HTTPException(status_code=415, detail="Only PDF regulation files are accepted.")
    content = await file.read(settings.regulatory_max_upload_bytes + 1)
    if len(content) > settings.regulatory_max_upload_bytes:
        raise HTTPException(status_code=413, detail="The regulation PDF exceeds the upload size limit.")
    try:
        pages = extract_pdf_pages(content)
        extracted_credit_rules = extract_credit_rules(pages) + extract_credit_table_rules(content)
        extracted_courses = extract_courses_from_pdf(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    document_id = uuid.uuid4()
    storage_key = f"{uuid.uuid4()}.pdf"
    storage_directory = settings.regulatory_storage_dir.resolve()
    storage_directory.mkdir(parents=True, exist_ok=True)
    destination = storage_directory / storage_key
    destination.write_bytes(content)
    document = RegulatoryDocument(
        id=document_id,
        title=title.strip(),
        category=RegulatoryCategory.OTHER,
        issuing_authority=issuing_authority.strip(),
        version=version.strip(),
        year=year,
        programme_level=programme_level,
        effective_date=date(year, 1, 1),
        applicability=programme_level.upper(),
        original_filename=file.filename[:255],
        storage_key=storage_key,
        mime_type="application/pdf",
        sha256=hashlib.sha256(content).hexdigest(),
        file_size=len(content),
        page_count=len(pages),
        chunk_count=0,
        extracted_text="\n".join(pages),
        extraction_warnings=[],
        status=RegulatoryDocumentStatus.READY,
        uploaded_by=admin.id,
    )
    document.rules = [
        RegulatoryRule(
            clause=item["clause"],
            page_number=item["page_number"],
            text=item["text"],
            rule_type=item["rule_type"],
            category=item["category"],
            semester=item["semester"],
            programme_duration_years=item.get("programme_duration_years"),
            value=item["value"],
            embedding=None,
            verification_status=RuleVerificationStatus.PENDING,
            has_conflict=False,
        )
        for item in extracted_credit_rules
    ]
    existing_codes = {
        code.casefold()
        for (code,) in db.query(Course.course_code).all()
    }
    courses = [
        Course(
            **item,
            course_type="theory",
            description="",
            objectives=[],
            prerequisites=[],
            programme_ids=[],
            status="active",
            created_by=admin.id,
            source_document_id=document_id,
        )
        for item in extracted_courses
        if item["course_code"].casefold() not in existing_codes
    ]
    db.add(document)
    db.flush()
    db.add_all(courses)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Regulatory document could not be saved.") from exc
    db.refresh(document)
    return document_response(document, courses_imported=len(courses))


@router.get("/api/regulations/{document_id}/download")
def download_regulatory_document(
    document_id: uuid.UUID,
    db: DbSession,
    _admin: User = Depends(AdminUser),
) -> FileResponse:
    document = db.get(RegulatoryDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Regulatory document not found")
    path = (settings.regulatory_storage_dir.resolve() / document.storage_key).resolve()
    if path.parent != settings.regulatory_storage_dir.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Stored regulatory document is unavailable")
    return FileResponse(path, media_type="application/pdf", filename=document.original_filename)


@router.delete("/api/regulations/{document_id}", status_code=204)
def delete_regulatory_document(
    document_id: uuid.UUID,
    db: DbSession,
    _admin: User = Depends(AdminUser),
) -> None:
    document = db.get(RegulatoryDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Regulatory document not found")

    storage_directory = settings.regulatory_storage_dir.resolve()
    path = (storage_directory / document.storage_key).resolve()
    if path.parent != storage_directory:
        raise HTTPException(status_code=500, detail="Stored regulatory document path is invalid")

    db.delete(document)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Regulatory document could not be deleted.") from exc

    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Regulatory record was deleted, but its stored PDF could not be removed.",
        ) from exc


@rules_router.get("", response_model=list[RegulatoryRuleResponse])
def list_regulatory_rules(
    db: DbSession,
    _admin: User = Depends(AdminUser),
    document_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status", pattern="^(applied|informational|ignored)$"),
    search: str | None = Query(default=None, max_length=300),
    issuing_authority: str | None = Query(default=None, max_length=200),
    year: int | None = Query(default=None, ge=1900, le=2200),
    programme_level: str | None = Query(default=None, pattern="^(ug|pg)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RegulatoryRuleResponse]:
    query = db.query(RegulatoryRule).join(RegulatoryDocument).options(*_rule_load_options())
    if document_id:
        query = query.filter(RegulatoryRule.document_id == document_id)
    if status_filter:
        if status_filter == "ignored":
            query = query.filter(RegulatoryRule.verification_status == RuleVerificationStatus.REJECTED)
        elif status_filter == "applied":
            query = query.filter(
                RegulatoryRule.verification_status != RuleVerificationStatus.REJECTED,
                RegulatoryRule.value.is_not(None),
                or_(
                    RegulatoryRule.rule_type.in_(("total_min", "total_max")),
                    (
                        RegulatoryRule.rule_type.in_(("category_min", "category_max", "category_total"))
                        & RegulatoryRule.category.is_not(None)
                    ),
                    (
                        RegulatoryRule.rule_type.in_(("semester_min", "semester_max", "semester_total"))
                        & RegulatoryRule.semester.is_not(None)
                    ),
                ),
                or_(
                    RegulatoryDocument.programme_level.is_not(None),
                    RegulatoryDocument.applicability.ilike("all applicable programmes"),
                ),
                RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
            )
        else:
            query = query.filter(
                RegulatoryRule.verification_status != RuleVerificationStatus.REJECTED,
                or_(
                    RegulatoryRule.value.is_(None),
                    RegulatoryRule.rule_type.is_(None),
                    ~RegulatoryRule.rule_type.in_(
                        (
                            "category_min",
                            "category_max",
                            "category_total",
                            "semester_min",
                            "semester_max",
                            "semester_total",
                            "total_min",
                            "total_max",
                        )
                    ),
                    (
                        RegulatoryRule.rule_type.in_(("category_min", "category_max", "category_total"))
                        & RegulatoryRule.category.is_(None)
                    ),
                    (
                        RegulatoryRule.rule_type.in_(("semester_min", "semester_max", "semester_total"))
                        & RegulatoryRule.semester.is_(None)
                    ),
                    and_(
                        RegulatoryDocument.programme_level.is_(None),
                        ~RegulatoryDocument.applicability.ilike("all applicable programmes"),
                    ),
                    RegulatoryDocument.status != RegulatoryDocumentStatus.READY,
                ),
            )
    if search:
        query = query.filter(RegulatoryRule.text.ilike(f"%{search.strip()}%"))
    if issuing_authority:
        query = query.filter(RegulatoryDocument.issuing_authority.ilike(f"%{issuing_authority.strip()}%"))
    if year is not None:
        query = query.filter(RegulatoryDocument.year == year)
    if programme_level:
        query = query.filter(RegulatoryDocument.programme_level == programme_level)
    rules = query.order_by(RegulatoryRule.created_at.desc()).offset(offset).limit(limit).all()
    return [rule_response(rule) for rule in rules]


@rules_router.patch("/{rule_id}", response_model=RegulatoryRuleResponse)
def update_regulatory_rule(
    rule_id: uuid.UUID,
    payload: RegulatoryRuleUpdate,
    db: DbSession,
    _admin: User = Depends(AdminUser),
) -> RegulatoryRuleResponse:
    rule = db.query(RegulatoryRule).options(*_rule_load_options()).filter(RegulatoryRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Regulatory rule not found")
    for field, value in payload.model_dump().items():
        setattr(rule, field, value)
    rule.verification_status = RuleVerificationStatus.PENDING
    rule.verified_by = None
    rule.verified_at = None
    db.commit()
    return rule_response(rule)


@rules_router.patch("/{rule_id}/decision", response_model=RegulatoryRuleResponse)
def decide_regulatory_rule(
    rule_id: uuid.UUID,
    payload: RegulatoryRuleDecision,
    db: DbSession,
    admin: User = Depends(AdminUser),
) -> RegulatoryRuleResponse:
    rule = db.query(RegulatoryRule).options(*_rule_load_options()).filter(RegulatoryRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Regulatory rule not found")
    if payload.status == "approved" and (rule.rule_type == "other" or rule.value is None):
        raise HTTPException(status_code=422, detail="Complete the rule type and numeric credit value before approval.")
    rule.verification_status = RuleVerificationStatus.VERIFIED if payload.status == "approved" else RuleVerificationStatus.REJECTED
    rule.verified_by = admin.id if payload.status == "approved" else None
    rule.verified_at = datetime.now(timezone.utc) if payload.status == "approved" else None
    db.commit()
    return rule_response(rule)
