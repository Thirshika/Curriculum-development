import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, load_only

from app.dependencies import DbSession, require_role
from app.models import CreditTableOverride, Programme, RegulatoryDocument, RegulatoryDocumentStatus, RegulatoryRule, RuleVerificationStatus, User, UserRole
from app.schemas import CreditTableOverrideCreate, CreditTableResponse, CreditTableRow, CreditTableSource

router = APIRouter(prefix="/api/credit-table", tags=["credit-table"])
AdminUser = Depends(require_role(UserRole.ADMIN))


def _scope_for_rule(rule: RegulatoryRule) -> tuple[str, str, str | None, int | None, str] | None:
    rule_type = rule.rule_type or ""
    if rule_type.startswith("category_") and rule.category:
        limit_type = {
            "category_min": "minimum",
            "category_max": "maximum",
            "category_total": "total",
        }.get(rule_type)
        if limit_type is None:
            return None
        return "category", f"category:{rule.category.casefold()}", rule.category, None, limit_type
    if rule_type.startswith("semester_") and rule.semester is not None:
        limit_type = {
            "semester_min": "minimum",
            "semester_max": "maximum",
            "semester_total": "total",
        }.get(rule_type)
        if limit_type:
            return "semester", f"semester:{rule.semester}", None, rule.semester, limit_type
    if rule_type in {"total_min", "total_max"}:
        limit_type = "minimum" if rule_type == "total_min" else "maximum"
        return "total", "total:all", None, None, limit_type
    return None


def _source(
    rule: RegulatoryRule | None = None,
    *,
    manual: bool = False,
    override_id: uuid.UUID | None = None,
) -> CreditTableSource:
    return CreditTableSource(
        rule_id=rule.id if rule else None,
        document_id=rule.document_id if rule else None,
        rule_text=rule.text if rule else None,
        page_number=rule.page_number if rule else None,
        manual=manual,
        override_id=override_id,
    )


def get_credit_table(db: DbSession, programme_level: str) -> CreditTableResponse:
    rows_by_key: dict[tuple[str, str], dict] = {}
    rules = (
        db.query(RegulatoryRule)
        .join(RegulatoryDocument)
        .options(
            load_only(
                RegulatoryRule.id,
                RegulatoryRule.document_id,
                RegulatoryRule.clause,
                RegulatoryRule.text,
                RegulatoryRule.page_number,
                RegulatoryRule.rule_type,
                RegulatoryRule.category,
                RegulatoryRule.semester,
                RegulatoryRule.programme_duration_years,
                RegulatoryRule.value,
                RegulatoryRule.verification_status,
                RegulatoryRule.verified_at,
                RegulatoryRule.created_at,
            ),
            joinedload(RegulatoryRule.document).load_only(
                RegulatoryDocument.id,
                RegulatoryDocument.programme_level,
                RegulatoryDocument.status,
                RegulatoryDocument.applicability,
            ),
        )
        .filter(
            RegulatoryRule.verification_status != RuleVerificationStatus.REJECTED,
            RegulatoryRule.programme_duration_years.is_(None),
            or_(
                RegulatoryDocument.programme_level == programme_level,
                RegulatoryDocument.applicability.ilike("all applicable programmes"),
            ),
            RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
        )
        .order_by(RegulatoryRule.verified_at.desc(), RegulatoryRule.created_at.desc())
        .all()
    )
    table_limit_keys = set()
    for rule in rules:
        if rule.clause != "Credit requirement table":
            continue
        scope = _scope_for_rule(rule)
        if scope is None or rule.value is None:
            continue
        scope_type, scope_key, _, _, limit_type = scope
        value_field = "total" if limit_type == "total" else limit_type
        table_limit_keys.add((scope_type, scope_key, value_field))

    for rule in rules:
        scope = _scope_for_rule(rule)
        if scope is None or rule.value is None:
            continue
        scope_type, scope_key, category, semester, limit_type = scope
        key = (scope_type, scope_key)
        row = rows_by_key.setdefault(
            key,
            {
                "scope_type": scope_type,
                "category": category,
                "semester": semester,
                "programme_level": programme_level,
                "minimum": None,
                "maximum": None,
                "total": None,
                "minimum_source": None,
                "maximum_source": None,
                "total_source": None,
            },
        )
        value_field = "total" if limit_type == "total" else limit_type
        if (
            rule.clause != "Credit requirement table"
            and (scope_type, scope_key, value_field) in table_limit_keys
        ):
            continue
        current = row[value_field]
        is_tighter = current is None or (
            limit_type == "minimum" and rule.value > current
        ) or (limit_type == "maximum" and rule.value < current)
        if is_tighter:
            row[value_field] = rule.value
            row[f"{value_field}_source"] = _source(rule)

    overrides = db.query(CreditTableOverride).filter(
        CreditTableOverride.programme_level == programme_level
    ).all()
    for override in overrides:
        key = (override.scope_type, override.scope_key)
        row = rows_by_key.setdefault(
            key,
            {
                "scope_type": override.scope_type,
                "category": override.category,
                "semester": override.semester,
                "programme_level": programme_level,
                "minimum": None,
                "maximum": None,
                "total": None,
                "minimum_source": None,
                "maximum_source": None,
                "total_source": None,
            },
        )
        field = "total" if override.limit_type == "total" else override.limit_type
        row[field] = override.value
        row[f"{field}_source"] = _source(manual=True, override_id=override.id)

    ordered = sorted(
        rows_by_key.values(),
        key=lambda row: (
            {"category": 0, "semester": 1, "total": 2}[row["scope_type"]],
            (row["category"] or "").casefold(),
            row["semester"] or 0,
        ),
    )
    return CreditTableResponse(
        programme_level=programme_level,
        rows=[CreditTableRow(**row) for row in ordered],
    )


def _broad_category_names(db: DbSession, programme_level: str) -> set[str]:
    categories = (
        db.query(RegulatoryRule.category)
        .join(RegulatoryDocument)
        .filter(
            RegulatoryRule.clause == "Credit requirement table",
            RegulatoryRule.rule_type.in_({"category_min", "category_max"}),
            RegulatoryRule.category.isnot(None),
            RegulatoryRule.verification_status != RuleVerificationStatus.REJECTED,
            or_(
                RegulatoryDocument.programme_level == programme_level,
                RegulatoryDocument.applicability.ilike("all applicable programmes"),
            ),
            RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
        )
        .distinct()
        .all()
    )
    return {category.casefold() for (category,) in categories if category}


def _degree_credit_table(
    db: DbSession,
    programme_level: str,
    duration_years: int,
) -> CreditTableResponse:
    rules = (
        db.query(RegulatoryRule)
        .join(RegulatoryDocument)
        .options(
            load_only(
                RegulatoryRule.id,
                RegulatoryRule.document_id,
                RegulatoryRule.text,
                RegulatoryRule.page_number,
                RegulatoryRule.rule_type,
                RegulatoryRule.category,
                RegulatoryRule.programme_duration_years,
                RegulatoryRule.value,
            )
        )
        .filter(
            RegulatoryRule.clause == "Credit requirement table",
            RegulatoryRule.programme_duration_years == duration_years,
            RegulatoryRule.verification_status != RuleVerificationStatus.REJECTED,
            or_(
                RegulatoryDocument.programme_level == programme_level,
                RegulatoryDocument.applicability.ilike("all applicable programmes"),
            ),
            RegulatoryDocument.status == RegulatoryDocumentStatus.READY,
        )
        .order_by(
            RegulatoryDocument.created_at.desc(),
            RegulatoryRule.page_number,
            RegulatoryRule.created_at,
        )
        .all()
    )
    latest_document_id = rules[0].document_id if rules else None
    rules = [rule for rule in rules if rule.document_id == latest_document_id]
    grouped_rules: dict[str, dict[str, RegulatoryRule]] = {}
    categories: dict[str, str] = {}
    total_rule = None
    for rule in rules:
        if rule.rule_type == "total_min":
            total_rule = rule
            continue
        if not rule.category:
            continue
        key = rule.category.casefold()
        categories[key] = rule.category
        group = grouped_rules.setdefault(key, {})
        current = group.get(rule.rule_type or "")
        if current is None or (
            rule.rule_type == "category_min"
            and current.value is None
            and rule.value is not None
        ):
            group[rule.rule_type or ""] = rule

    overrides = {
        override.scope_key: override
        for override in db.query(CreditTableOverride).filter(
            CreditTableOverride.programme_level == programme_level,
            CreditTableOverride.scope_type == "category",
            CreditTableOverride.limit_type == "maximum",
        )
    }
    rows = []
    for key, category in categories.items():
        group = grouped_rules[key]
        minimum_rule = group.get("category_min")
        if minimum_rule is None:
            continue
        match = re.search(
            r"minimum credit requirement:\s*(.*?)\s+credits\.",
            minimum_rule.text,
            re.IGNORECASE,
        )
        credit_value = match.group(1).strip() if match else None
        if credit_value == "-":
            credit_value = "—"
        manual_maximum = overrides.get(f"category:{key}")
        rows.append(
            CreditTableRow(
                scope_type="category",
                category=category,
                semester=None,
                programme_level=programme_level,
                programme_duration_years=duration_years,
                credit_value=credit_value,
                minimum=minimum_rule.value,
                maximum=manual_maximum.value if manual_maximum else None,
                total=None,
                minimum_source=_source(minimum_rule),
                maximum_source=_source(manual=True, override_id=manual_maximum.id) if manual_maximum else None,
                total_source=None,
            )
        )
    if total_rule is not None:
        total_match = re.search(
            r"total minimum credit requirement:\s*(.*?)\s+credits\.",
            total_rule.text,
            re.IGNORECASE,
        )
        total_value = total_match.group(1).strip() if total_match else None
        rows.append(
            CreditTableRow(
                scope_type="total",
                category=None,
                semester=None,
                programme_level=programme_level,
                programme_duration_years=duration_years,
                credit_value=total_value,
                minimum=total_rule.value,
                maximum=None,
                total=None,
                minimum_source=_source(total_rule),
                maximum_source=None,
                total_source=None,
            )
        )
    rows.sort(key=lambda row: (row.scope_type == "total", (row.category or "").casefold()))
    return CreditTableResponse(programme_level=programme_level, rows=rows)


def get_programme_credit_table(db: Session, programme: Programme) -> CreditTableResponse | None:
    programme_level = programme.level.value
    if programme_level not in {"ug", "pg"}:
        return None
    duration = int(programme.duration_years) if programme.duration_years % 1 == 0 else None
    if duration in {3, 4}:
        return _degree_credit_table(db, programme_level, duration)
    return get_credit_table(db, programme_level)


@router.get("", response_model=CreditTableResponse)
def list_credit_table(
    db: DbSession,
    _admin: User = AdminUser,
    programme_level: str = Query(default="ug", pattern="^(ug|pg)$"),
    duration_years: int | None = Query(default=None, ge=3, le=4),
) -> CreditTableResponse:
    if duration_years is not None:
        return _degree_credit_table(db, programme_level, duration_years)
    broad_categories = _broad_category_names(db, programme_level)
    table = get_credit_table(db, programme_level)
    return table.model_copy(
        update={
            "rows": [
                row.model_copy(
                    update={
                        "maximum": row.maximum if row.maximum_source and row.maximum_source.manual else None,
                        "maximum_source": row.maximum_source if row.maximum_source and row.maximum_source.manual else None,
                        "total": None,
                        "total_source": None,
                    }
                )
                for row in table.rows
                if row.scope_type == "category"
                and row.category
                and row.category.casefold() in broad_categories
            ]
        }
    )


@router.put("/overrides", response_model=CreditTableResponse)
def set_credit_table_override(
    payload: CreditTableOverrideCreate,
    db: DbSession,
    admin: User = AdminUser,
) -> CreditTableResponse:
    if payload.scope_type != "category" or payload.limit_type != "maximum":
        raise HTTPException(
            status_code=422,
            detail="Only maximum overrides for broad course categories are supported.",
        )
    broad_categories = _broad_category_names(db, payload.programme_level)
    if payload.category is None or payload.category.casefold() not in broad_categories:
        raise HTTPException(
            status_code=422,
            detail="Select a broad course category from an uploaded credit requirement table.",
        )

    scope_key = (
        f"category:{payload.category.casefold()}"
    )
    override = db.query(CreditTableOverride).filter(
        CreditTableOverride.programme_level == payload.programme_level,
        CreditTableOverride.scope_key == scope_key,
        CreditTableOverride.limit_type == payload.limit_type,
    ).first()
    if override is None:
        override = CreditTableOverride(
            programme_level=payload.programme_level,
            scope_type=payload.scope_type,
            scope_key=scope_key,
            category=payload.category,
            semester=payload.semester,
            limit_type=payload.limit_type,
            value=payload.value,
            updated_by=admin.id,
        )
        db.add(override)
    else:
        override.value = payload.value
        override.updated_by = admin.id
    db.commit()
    return list_credit_table(db, admin, payload.programme_level, None)


@router.delete("/overrides/{override_id}", response_model=CreditTableResponse)
def delete_credit_table_override(
    override_id: uuid.UUID,
    db: DbSession,
    _admin: User = AdminUser,
) -> CreditTableResponse:
    override = db.get(CreditTableOverride, override_id)
    if override is None:
        raise HTTPException(status_code=404, detail="Credit table override not found")
    programme_level = override.programme_level
    db.delete(override)
    db.commit()
    return list_credit_table(db, _admin, programme_level, None)
