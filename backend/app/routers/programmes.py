import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.credit_engine import ConstraintEvidence, validate_credit_plan
from app.dependencies import DbSession, require_role
from app.models import (
    College,
    CreditConstraint,
    CreditConstraintKind,
    CreditValidationRun,
    Programme,
    ProgrammeLevel,
    ProgrammeRegulatoryMapping,
    ProgrammeStatus,
    RegulatoryCategory,
    RegulatoryDocument,
    RegulatoryDocumentStatus,
    RegulatoryRule,
    RuleVerificationStatus,
    University,
    UniversityStatus,
    User,
    UserRole,
)
from app.schemas import (
    CreditCheckResult,
    CreditValidationRequest,
    CreditValidationResponse,
    ProgrammeCreate,
    ProgrammeRegulatoryResponse,
    ProgrammeResponse,
    ProgrammeUpdate,
)

router = APIRouter(prefix="/api/programmes", tags=["programmes"])
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


def programme_query(db):
    return db.query(Programme).options(
        joinedload(Programme.university),
        joinedload(Programme.college),
        joinedload(Programme.regulatory_mappings).joinedload(ProgrammeRegulatoryMapping.document),
    )


def programme_response(db, programme: Programme) -> ProgrammeResponse:
    documents = [mapping.document for mapping in programme.regulatory_mappings]
    document_ids = [document.id for document in documents]
    verified_counts: dict[uuid.UUID, int] = {}
    constraints_by_document: dict[uuid.UUID, list[CreditConstraint]] = {document_id: [] for document_id in document_ids}
    if document_ids:
        counts = (
            db.query(RegulatoryRule.document_id, func.count(RegulatoryRule.id))
            .join(RegulatoryDocument, RegulatoryRule.document_id == RegulatoryDocument.id)
            .filter(
                RegulatoryRule.document_id.in_(document_ids),
                RegulatoryRule.verification_status == RuleVerificationStatus.VERIFIED,
                RegulatoryRule.has_conflict.is_(False),
                RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
            )
            .group_by(RegulatoryRule.document_id)
            .all()
        )
        verified_counts = {document_id: count for document_id, count in counts}
        constraints = (
            db.query(CreditConstraint)
            .join(RegulatoryRule)
            .join(RegulatoryDocument, RegulatoryRule.document_id == RegulatoryDocument.id)
            .options(joinedload(CreditConstraint.rule))
            .filter(
                RegulatoryRule.document_id.in_(document_ids),
                RegulatoryRule.verification_status == RuleVerificationStatus.VERIFIED,
                RegulatoryRule.has_conflict.is_(False),
                RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
            )
            .order_by(CreditConstraint.kind)
            .all()
        )
        for constraint in constraints:
            constraints_by_document[constraint.rule.document_id].append(constraint)

    regulatory_responses = []
    for document in documents:
        constraint_responses = []
        for constraint in constraints_by_document[document.id]:
            rule = constraint.rule
            constraint_responses.append(
                {
                    "id": constraint.id,
                    "rule_id": rule.id,
                    "kind": constraint.kind.value,
                    "value": constraint.value,
                    "rule_text": rule.text,
                    "clause": rule.clause,
                    "page_number": rule.page_number,
                    "document_id": document.id,
                    "document_title": document.title,
                    "document_category": document.category.value,
                    "document_version": document.version,
                    "effective_date": document.effective_date,
                    "applicability": document.applicability,
                }
            )
        regulatory_responses.append(
            ProgrammeRegulatoryResponse(
                document_id=document.id,
                title=document.title,
                category=document.category.value,
                issuing_authority=document.issuing_authority,
                version=document.version,
                effective_date=document.effective_date,
                applicability=document.applicability,
                status=document.status.value,
                verified_rule_count=verified_counts.get(document.id, 0),
                constraints=constraint_responses,
            )
        )
    return ProgrammeResponse(
        id=programme.id,
        university_id=programme.university_id,
        college_id=programme.college_id,
        college_name=programme.college.name if programme.college else None,
        university_name=programme.university.name,
        university_code=programme.university.code,
        name=programme.name,
        degree_type=programme.degree_type,
        specialization=programme.specialization,
        level=programme.level.value,
        duration_years=programme.duration_years,
        semester_count=programme.semester_count,
        academic_year=programme.academic_year,
        qualification_level=programme.qualification_level,
        status=programme.status.value,
        created_at=programme.created_at,
        updated_at=programme.updated_at,
        applicable_regulations=regulatory_responses,
    )


def set_regulatory_mappings(db, programme: Programme, document_ids: list[uuid.UUID]) -> None:
    unique_ids = list(dict.fromkeys(document_ids))
    existing_mappings = {mapping.document_id: mapping for mapping in programme.regulatory_mappings}
    existing_ids = set(existing_mappings)
    desired_ids = set(unique_ids)
    documents = db.query(RegulatoryDocument).filter(RegulatoryDocument.id.in_(unique_ids)).all()
    found = {document.id: document for document in documents}
    missing = [document_id for document_id in unique_ids if document_id not in found]
    if missing:
        raise HTTPException(status_code=422, detail="One or more selected regulatory documents do not exist")
    for document in documents:
        if document.status != RegulatoryDocumentStatus.READY and document.id not in existing_ids:
            raise HTTPException(status_code=409, detail=f"Archived source “{document.title}” cannot be newly applied")
        if document.category == RegulatoryCategory.UNIVERSITY and document.university_id != programme.university_id:
            raise HTTPException(
                status_code=403,
                detail=f"University regulation “{document.title}” belongs to a different university",
            )
    programme.regulatory_mappings[:] = [
        mapping for document_id, mapping in existing_mappings.items() if document_id in desired_ids
    ]
    programme.regulatory_mappings.extend(
        ProgrammeRegulatoryMapping(document_id=document_id)
        for document_id in unique_ids
        if document_id not in existing_ids
    )


@router.get("", response_model=list[ProgrammeResponse])
def list_programmes(
    db: DbSession,
    _admin: AdminUser,
    university_id: uuid.UUID | None = None,
    college_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, max_length=120),
    programme_status: str | None = Query(default=None, alias="status", pattern="^(active|inactive)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[ProgrammeResponse]:
    query = programme_query(db)
    if university_id:
        query = query.filter(Programme.university_id == university_id)
    if college_id:
        query = query.filter(Programme.college_id == college_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.join(University).filter(
            or_(Programme.name.ilike(pattern), Programme.degree_type.ilike(pattern), University.name.ilike(pattern))
        )
    if programme_status:
        query = query.filter(Programme.status == ProgrammeStatus(programme_status))
    programmes = query.order_by(Programme.updated_at.desc()).offset(offset).limit(limit).all()
    return [programme_response(db, programme) for programme in programmes]


@router.post("", response_model=ProgrammeResponse, status_code=status.HTTP_201_CREATED)
def create_programme(
    payload: ProgrammeCreate,
    db: DbSession,
    admin: AdminUser,
) -> ProgrammeResponse:
    university = db.get(University, payload.university_id)
    if university is None:
        raise HTTPException(status_code=404, detail="University not found")
    if university.status != UniversityStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Activate the university before creating programmes")
    college = None
    if payload.college_id:
        college = db.query(College).filter(
            College.id == payload.college_id,
            College.university_id == university.id,
            College.status == "active",
        ).first()
        if college is None:
            raise HTTPException(status_code=422, detail="The selected college must be active and belong to this university.")
    programme = Programme(
        university_id=university.id,
        college_id=college.id if college else None,
        name=payload.name,
        degree_type=payload.degree_type,
        specialization=payload.specialization or None,
        level=ProgrammeLevel(payload.level.value),
        duration_years=payload.duration_years,
        semester_count=payload.semester_count,
        academic_year=payload.academic_year,
        qualification_level=payload.qualification_level or None,
        created_by=admin.id,
    )
    set_regulatory_mappings(db, programme, payload.regulatory_document_ids)
    db.add(programme)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This university already has a programme with that name for the academic year",
        ) from exc
    programme = programme_query(db).filter(Programme.id == programme.id).first()
    return programme_response(db, programme)


@router.patch("/{programme_id}", response_model=ProgrammeResponse)
def update_programme(
    programme_id: uuid.UUID,
    payload: ProgrammeUpdate,
    db: DbSession,
    _admin: AdminUser,
) -> ProgrammeResponse:
    programme = programme_query(db).filter(Programme.id == programme_id).first()
    if programme is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    updates = payload.model_dump(exclude_unset=True)
    document_ids = updates.pop("regulatory_document_ids", None)
    if "college_id" in updates and updates["college_id"] is not None:
        college = db.query(College).filter(
            College.id == updates["college_id"],
            College.university_id == programme.university_id,
            College.status == "active",
        ).first()
        if college is None:
            raise HTTPException(status_code=422, detail="The selected college must be active and belong to this programme's university.")
    for field, value in updates.items():
        if value is None and field in {"name", "degree_type", "level", "duration_years", "semester_count", "academic_year", "status"}:
            raise HTTPException(status_code=422, detail=f"{field} cannot be empty")
        if field == "level":
            value = ProgrammeLevel(value.value)
        if field == "status":
            value = ProgrammeStatus(value.value)
        if field in {"specialization", "qualification_level"} and value == "":
            value = None
        setattr(programme, field, value)
    if document_ids is not None:
        set_regulatory_mappings(db, programme, document_ids)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This university already has a programme with that name for the academic year",
        ) from exc
    programme = programme_query(db).filter(Programme.id == programme_id).first()
    return programme_response(db, programme)


def validation_response(run: CreditValidationRun) -> CreditValidationResponse:
    return CreditValidationResponse(
        id=run.id,
        programme_id=run.programme_id,
        semester_credits=[Decimal(value) for value in run.semester_credits],
        total_credits=run.total_credits,
        status=run.status,
        configured_constraint_count=run.configured_constraint_count,
        checks=[CreditCheckResult.model_validate(check) for check in run.checks],
        created_at=run.created_at,
    )


@router.post("/{programme_id}/validate-credits", response_model=CreditValidationResponse)
def validate_programme_credits(
    programme_id: uuid.UUID,
    payload: CreditValidationRequest,
    db: DbSession,
    admin: AdminUser,
) -> CreditValidationResponse:
    programme = programme_query(db).filter(Programme.id == programme_id).first()
    if programme is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    document_ids = [mapping.document_id for mapping in programme.regulatory_mappings]
    constraints: list[ConstraintEvidence] = []
    if document_ids:
        rows = (
            db.query(CreditConstraint, RegulatoryRule, RegulatoryDocument)
            .join(RegulatoryRule, CreditConstraint.rule_id == RegulatoryRule.id)
            .join(RegulatoryDocument, RegulatoryRule.document_id == RegulatoryDocument.id)
            .filter(
                RegulatoryDocument.id.in_(document_ids),
                RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
                RegulatoryRule.verification_status == RuleVerificationStatus.VERIFIED,
                RegulatoryRule.has_conflict.is_(False),
            )
            .all()
        )
        constraints = [
            ConstraintEvidence(
                rule_id=rule.id,
                document_id=document.id,
                document_title=document.title,
                clause=rule.clause,
                page_number=rule.page_number,
                version=document.version,
                kind=constraint.kind,
                value=constraint.value,
            )
            for constraint, rule, document in rows
        ]
    result_status, total_credits, checks = validate_credit_plan(
        duration_years=programme.duration_years,
        semester_count=programme.semester_count,
        semester_credits=payload.semester_credits,
        constraints=constraints,
    )
    run = CreditValidationRun(
        programme_id=programme.id,
        created_by=admin.id,
        semester_credits=[str(value) for value in payload.semester_credits],
        total_credits=total_credits,
        status=result_status,
        checks=checks,
        configured_constraint_count=len(constraints),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return validation_response(run)


@router.get("/{programme_id}/validations", response_model=list[CreditValidationResponse])
def list_credit_validations(
    programme_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[CreditValidationResponse]:
    if db.query(Programme.id).filter(Programme.id == programme_id).first() is None:
        raise HTTPException(status_code=404, detail="Programme not found")
    runs = (
        db.query(CreditValidationRun)
        .filter(CreditValidationRun.programme_id == programme_id)
        .order_by(CreditValidationRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [validation_response(run) for run in runs]
