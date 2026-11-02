import hashlib
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.config import settings
from app.dependencies import DbSession, require_role
from app.models import (
    CreditConstraint,
    CreditConstraintKind,
    RegulatoryCategory,
    RegulatoryChunk,
    RegulatoryDocument,
    RegulatoryDocumentStatus,
    RegulatoryRule,
    University,
    UniversityStatus,
    RuleVerificationStatus,
    User,
    UserRole,
)
from app.regulatory import (
    SUPPORTED_MIME_TYPES,
    candidate_rules,
    cosine_similarity,
    extract_document,
    local_embedding,
    read_upload,
    split_pages,
)
from app.schemas import (
    RegulatoryCategoryValue,
    RegulatoryDocumentResponse,
    RegulatoryRuleResponse,
    RegulatorySearchRequest,
    RegulatorySearchResult,
    RegulatoryTextResponse,
    RuleConflictUpdate,
    RuleVerificationUpdate,
    CreditConstraintResponse,
    CreditConstraintUpsert,
)

router = APIRouter(prefix="/api/regulations", tags=["regulations"])
rules_router = APIRouter(prefix="/api/regulatory-rules", tags=["regulatory-rules"])
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


def document_counts(db, document_id: uuid.UUID) -> Counter:
    rows = (
        db.query(RegulatoryRule.verification_status, func.count(RegulatoryRule.id))
        .filter(RegulatoryRule.document_id == document_id)
        .group_by(RegulatoryRule.verification_status)
        .all()
    )
    return Counter({status_value.value: count for status_value, count in rows})


def document_response(document: RegulatoryDocument, counts: Counter) -> RegulatoryDocumentResponse:
    return RegulatoryDocumentResponse(
        id=document.id,
        title=document.title,
        category=document.category.value,
        issuing_authority=document.issuing_authority,
        version=document.version,
        effective_date=document.effective_date,
        applicability=document.applicability,
        university_id=document.university_id,
        university_name=document.university.name if document.university else None,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size=document.file_size,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        status=document.status.value,
        extraction_warnings=document.extraction_warnings or [],
        pending_rules=counts["pending"],
        verified_rules=counts["verified"],
        rejected_rules=counts["rejected"],
        created_at=document.created_at,
        archived_at=document.archived_at,
    )


def rule_response(rule: RegulatoryRule) -> RegulatoryRuleResponse:
    document = rule.document
    return RegulatoryRuleResponse(
        id=rule.id,
        document_id=document.id,
        document_title=document.title,
        category=document.category.value,
        issuing_authority=document.issuing_authority,
        version=document.version,
        effective_date=document.effective_date,
        applicability=document.applicability,
        clause=rule.clause,
        page_number=rule.page_number,
        text=rule.text,
        verification_status=rule.verification_status.value,
        has_conflict=rule.has_conflict,
        conflict_note=rule.conflict_note,
        verified_by=rule.verified_by,
        verified_at=rule.verified_at,
    )


@router.get("", response_model=list[RegulatoryDocumentResponse])
def list_regulatory_documents(
    db: DbSession,
    _admin: AdminUser,
    search: str | None = Query(default=None, max_length=120),
    category: RegulatoryCategoryValue | None = None,
    document_status: str | None = Query(default=None, alias="status", pattern="^(ready|archived)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[RegulatoryDocumentResponse]:
    query = db.query(RegulatoryDocument)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                RegulatoryDocument.title.ilike(pattern),
                RegulatoryDocument.issuing_authority.ilike(pattern),
                RegulatoryDocument.version.ilike(pattern),
            )
        )
    if category:
        query = query.filter(RegulatoryDocument.category == RegulatoryCategory(category.value))
    if document_status:
        query = query.filter(RegulatoryDocument.status == RegulatoryDocumentStatus(document_status))
    documents = query.order_by(RegulatoryDocument.created_at.desc()).offset(offset).limit(limit).all()
    return [document_response(document, document_counts(db, document.id)) for document in documents]


@router.post("", response_model=RegulatoryDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_regulatory_document(
    db: DbSession,
    admin: AdminUser,
    file: Annotated[UploadFile, File()],
    category: Annotated[RegulatoryCategoryValue, Form()],
    issuing_authority: Annotated[str, Form(min_length=2, max_length=200)],
    version: Annotated[str, Form(min_length=1, max_length=80)],
    applicability: Annotated[str, Form(min_length=2, max_length=500)],
    title: Annotated[str | None, Form(max_length=240)] = None,
    effective_date: Annotated[str | None, Form()] = None,
    university_id: Annotated[uuid.UUID | None, Form()] = None,
) -> RegulatoryDocumentResponse:
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Only PDF and DOCX documents are supported")
    content = await read_upload(file, settings.regulatory_max_upload_bytes)
    extracted = extract_document(filename, content)
    cleaned_title = (title or Path(filename).stem).strip()
    cleaned_authority = issuing_authority.strip()
    cleaned_version = version.strip()
    cleaned_applicability = applicability.strip()
    if len(cleaned_title) < 2 or len(cleaned_authority) < 2 or not cleaned_version or len(cleaned_applicability) < 2:
        raise HTTPException(status_code=422, detail="Title, authority, version, and applicability must not be blank")
    if category == RegulatoryCategoryValue.UNIVERSITY and university_id is None:
        raise HTTPException(status_code=422, detail="Select the university this regulation applies to")
    if university_id is not None:
        university = db.get(University, university_id)
        if university is None:
            raise HTTPException(status_code=404, detail="University not found")
        if category != RegulatoryCategoryValue.UNIVERSITY:
            raise HTTPException(status_code=422, detail="Only university regulations can be scoped to a university")
        if university.status != UniversityStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="University-specific regulations require an active university")

    duplicate = db.query(RegulatoryDocument.id).filter(
        func.lower(RegulatoryDocument.title) == cleaned_title.lower(),
        RegulatoryDocument.category == RegulatoryCategory(category.value),
        RegulatoryDocument.version == cleaned_version,
        RegulatoryDocument.university_id == university_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="This regulatory document version already exists")

    chunks = split_pages(extracted.pages, settings.regulatory_chunk_size, settings.regulatory_chunk_overlap)
    if not chunks:
        raise HTTPException(status_code=422, detail="No searchable text could be extracted from the document")
    candidates = candidate_rules(extracted.pages)
    storage_key = f"{uuid.uuid4()}{suffix}"
    storage_directory = settings.regulatory_storage_dir.resolve()
    storage_directory.mkdir(parents=True, exist_ok=True)
    destination = storage_directory / storage_key
    destination.write_bytes(content)
    parsed_effective_date = None
    if effective_date:
        try:
            parsed_effective_date = datetime.strptime(effective_date, "%Y-%m-%d").date()
        except ValueError as exc:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="Effective date must use YYYY-MM-DD format") from exc
    document = RegulatoryDocument(
        title=cleaned_title,
        category=RegulatoryCategory(category.value),
        issuing_authority=cleaned_authority,
        version=cleaned_version,
        effective_date=parsed_effective_date,
        applicability=cleaned_applicability,
        university_id=university_id,
        original_filename=filename[:255],
        storage_key=storage_key,
        mime_type=SUPPORTED_MIME_TYPES[suffix],
        sha256=hashlib.sha256(content).hexdigest(),
        file_size=len(content),
        page_count=extracted.page_count,
        chunk_count=len(chunks),
        extracted_text="\n\n".join(page.text for page in extracted.pages if page.text.strip()),
        extraction_warnings=extracted.warnings,
        status=RegulatoryDocumentStatus.READY,
        uploaded_by=admin.id,
    )
    for index, (page_number, chunk_text) in enumerate(chunks):
        document.chunks.append(
            RegulatoryChunk(
                chunk_index=index,
                page_number=page_number,
                content=chunk_text,
                embedding=local_embedding(chunk_text),
            )
        )
    for clause, page_number, rule_text in candidates:
        document.rules.append(
            RegulatoryRule(
                clause=clause,
                page_number=page_number,
                text=rule_text,
                embedding=local_embedding(rule_text),
                verification_status=RuleVerificationStatus.PENDING,
            )
        )
    db.add(document)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="This regulatory document version already exists") from exc
    except SQLAlchemyError:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    db.refresh(document)
    return document_response(document, Counter({"pending": len(candidates)}))


@router.get("/{document_id}", response_model=RegulatoryDocumentResponse)
def get_regulatory_document(
    document_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
) -> RegulatoryDocumentResponse:
    document = db.get(RegulatoryDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Regulatory document not found")
    return document_response(document, document_counts(db, document.id))


@router.get("/{document_id}/text", response_model=RegulatoryTextResponse)
def get_extracted_document_text(
    document_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
) -> RegulatoryTextResponse:
    document = db.get(RegulatoryDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Regulatory document not found")
    return RegulatoryTextResponse(
        document_id=document.id,
        title=document.title,
        extracted_text=document.extracted_text,
    )


@router.get("/{document_id}/download")
def download_regulatory_document(
    document_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
) -> FileResponse:
    document = db.get(RegulatoryDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Regulatory document not found")
    storage_directory = settings.regulatory_storage_dir.resolve()
    file_path = (storage_directory / document.storage_key).resolve()
    if file_path.parent != storage_directory or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored regulatory document is unavailable")
    return FileResponse(
        path=file_path,
        media_type=document.mime_type,
        filename=document.original_filename,
        content_disposition_type="attachment",
    )


@router.post("/{document_id}/archive", response_model=RegulatoryDocumentResponse)
def archive_regulatory_document(
    document_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
) -> RegulatoryDocumentResponse:
    document = db.get(RegulatoryDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Regulatory document not found")
    if document.status == RegulatoryDocumentStatus.READY:
        document.status = RegulatoryDocumentStatus.ARCHIVED
        document.archived_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(document)
    return document_response(document, document_counts(db, document.id))


@rules_router.get("", response_model=list[RegulatoryRuleResponse])
def list_regulatory_rules(
    db: DbSession,
    _admin: AdminUser,
    document_id: uuid.UUID | None = None,
    verification_status: str | None = Query(default=None, pattern="^(pending|verified|rejected)$"),
    conflicts_only: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[RegulatoryRuleResponse]:
    query = db.query(RegulatoryRule).options(joinedload(RegulatoryRule.document))
    if document_id:
        query = query.filter(RegulatoryRule.document_id == document_id)
    if verification_status:
        query = query.filter(RegulatoryRule.verification_status == RuleVerificationStatus(verification_status))
    if conflicts_only:
        query = query.filter(RegulatoryRule.has_conflict.is_(True))
    rules = query.order_by(RegulatoryRule.created_at.desc()).offset(offset).limit(limit).all()
    return [rule_response(rule) for rule in rules]


@rules_router.patch("/{rule_id}/verification", response_model=RegulatoryRuleResponse)
def verify_regulatory_rule(
    rule_id: uuid.UUID,
    payload: RuleVerificationUpdate,
    db: DbSession,
    admin: AdminUser,
) -> RegulatoryRuleResponse:
    rule = (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.document))
        .filter(RegulatoryRule.id == rule_id)
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Regulatory rule not found")
    if rule.document.status != RegulatoryDocumentStatus.READY:
        raise HTTPException(status_code=409, detail="Rules from archived documents cannot be verified")
    rule.verification_status = RuleVerificationStatus(payload.verification_status)
    rule.verified_by = admin.id
    rule.verified_at = datetime.now(timezone.utc)
    db.commit()
    return rule_response(rule)


@rules_router.patch("/{rule_id}/conflict", response_model=RegulatoryRuleResponse)
def flag_regulatory_rule_conflict(
    rule_id: uuid.UUID,
    payload: RuleConflictUpdate,
    db: DbSession,
    _admin: AdminUser,
) -> RegulatoryRuleResponse:
    rule = (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.document))
        .filter(RegulatoryRule.id == rule_id)
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Regulatory rule not found")
    rule.has_conflict = payload.has_conflict
    rule.conflict_note = payload.conflict_note.strip() if payload.has_conflict and payload.conflict_note else None
    db.commit()
    return rule_response(rule)


def credit_constraint_response(constraint: CreditConstraint) -> CreditConstraintResponse:
    rule = constraint.rule
    document = rule.document
    return CreditConstraintResponse(
        id=constraint.id,
        rule_id=rule.id,
        kind=constraint.kind.value,
        value=constraint.value,
        rule_text=rule.text,
        clause=rule.clause,
        page_number=rule.page_number,
        document_id=document.id,
        document_title=document.title,
        document_category=document.category.value,
        document_version=document.version,
        effective_date=document.effective_date,
        applicability=document.applicability,
    )


@rules_router.put("/{rule_id}/credit-constraint", response_model=CreditConstraintResponse)
def set_credit_constraint(
    rule_id: uuid.UUID,
    payload: CreditConstraintUpsert,
    db: DbSession,
    admin: AdminUser,
) -> CreditConstraintResponse:
    rule = (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.document))
        .filter(RegulatoryRule.id == rule_id)
        .first()
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Regulatory rule not found")
    if (
        rule.verification_status != RuleVerificationStatus.VERIFIED
        or rule.has_conflict
        or rule.document.status != RegulatoryDocumentStatus.READY
    ):
        raise HTTPException(
            status_code=409,
            detail="Configure constraints only from verified, unconflicted rules in active documents",
        )
    constraint = (
        db.query(CreditConstraint)
        .filter(CreditConstraint.rule_id == rule.id, CreditConstraint.kind == CreditConstraintKind(payload.kind.value))
        .first()
    )
    if constraint is None:
        constraint = CreditConstraint(
            rule_id=rule.id,
            kind=CreditConstraintKind(payload.kind.value),
            value=payload.value,
            created_by=admin.id,
        )
        db.add(constraint)
    else:
        constraint.value = payload.value
    db.commit()
    db.refresh(constraint)
    constraint.rule = rule
    return credit_constraint_response(constraint)


@rules_router.get("/credit-constraints", response_model=list[CreditConstraintResponse])
def list_credit_constraints(
    db: DbSession,
    _admin: AdminUser,
    document_id: uuid.UUID | None = None,
) -> list[CreditConstraintResponse]:
    query = (
        db.query(CreditConstraint)
        .join(RegulatoryRule)
        .join(RegulatoryDocument)
        .options(joinedload(CreditConstraint.rule).joinedload(RegulatoryRule.document))
        .filter(
            RegulatoryRule.verification_status == RuleVerificationStatus.VERIFIED,
            RegulatoryRule.has_conflict.is_(False),
            RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
        )
    )
    if document_id:
        query = query.filter(RegulatoryDocument.id == document_id)
    constraints = query.order_by(RegulatoryDocument.title, RegulatoryRule.page_number).all()
    return [credit_constraint_response(constraint) for constraint in constraints]


@rules_router.post("/retrieve", response_model=list[RegulatorySearchResult])
def retrieve_verified_rules(
    payload: RegulatorySearchRequest,
    db: DbSession,
    _admin: AdminUser,
) -> list[RegulatorySearchResult]:
    query = (
        db.query(RegulatoryRule)
        .join(RegulatoryDocument)
        .options(joinedload(RegulatoryRule.document))
        .filter(
            RegulatoryRule.verification_status == RuleVerificationStatus.VERIFIED,
            RegulatoryRule.has_conflict.is_(False),
            RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
        )
    )
    if payload.categories:
        categories = [RegulatoryCategory(category.value) for category in payload.categories]
        query = query.filter(RegulatoryDocument.category.in_(categories))
    vector = local_embedding(payload.query)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        rows = query.with_entities(
            RegulatoryRule,
            RegulatoryRule.embedding.cosine_distance(vector).label("distance"),
        ).order_by("distance").limit(payload.top_k).all()
        ranked = [(1 - distance, rule) for rule, distance in rows]
    else:
        ranked = sorted(
            ((cosine_similarity(vector, rule.embedding), rule) for rule in query.all()),
            key=lambda item: item[0],
            reverse=True,
        )
    return [
        RegulatorySearchResult(
            rule_id=rule.id,
            document_id=rule.document.id,
            title=rule.document.title,
            category=rule.document.category.value,
            issuing_authority=rule.document.issuing_authority,
            version=rule.document.version,
            effective_date=rule.document.effective_date,
            applicability=rule.document.applicability,
            clause=rule.clause,
            page_number=rule.page_number,
            text=rule.text,
            similarity=round(similarity, 4),
            has_conflict=rule.has_conflict,
        )
        for similarity, rule in ranked[: payload.top_k]
        if similarity > 0
    ]
