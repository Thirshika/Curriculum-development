from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.models import CreditConstraintKind


@dataclass(frozen=True)
class ConstraintEvidence:
    rule_id: UUID
    document_id: UUID
    document_title: str
    clause: str | None
    page_number: int | None
    version: str
    kind: CreditConstraintKind
    value: Decimal


def validate_credit_plan(
    *,
    duration_years: Decimal,
    semester_count: int,
    semester_credits: list[Decimal],
    constraints: list[ConstraintEvidence],
) -> tuple[str, Decimal, list[dict[str, Any]]]:
    total_credits = sum(semester_credits, Decimal("0"))
    checks: list[dict[str, Any]] = []

    if len(semester_credits) != semester_count:
        checks.append(
            {
                "kind": None,
                "passed": False,
                "actual": str(len(semester_credits)),
                "expected": str(semester_count),
                "message": f"Expected a credit allocation for {semester_count} semesters, received {len(semester_credits)}.",
                "rule_id": None,
                "document_id": None,
                "document_title": None,
                "clause": None,
                "page_number": None,
                "version": None,
            }
        )

    for constraint in constraints:
        if constraint.kind == CreditConstraintKind.MIN_TOTAL_CREDITS:
            actual = total_credits
            passed = actual >= constraint.value
            expected = f">= {constraint.value}"
            subject = f"Total credits {actual}"
            unit = "credits"
        elif constraint.kind == CreditConstraintKind.MAX_TOTAL_CREDITS:
            actual = total_credits
            passed = actual <= constraint.value
            expected = f"<= {constraint.value}"
            subject = f"Total credits {actual}"
            unit = "credits"
        elif constraint.kind == CreditConstraintKind.MIN_SEMESTER_CREDITS:
            actual = min(semester_credits, default=Decimal("0"))
            passed = all(value >= constraint.value for value in semester_credits)
            expected = f"each semester >= {constraint.value}"
            subject = f"Minimum semester load {actual}"
            unit = "credits"
        elif constraint.kind == CreditConstraintKind.MAX_SEMESTER_CREDITS:
            actual = max(semester_credits, default=Decimal("0"))
            passed = all(value <= constraint.value for value in semester_credits)
            expected = f"each semester <= {constraint.value}"
            subject = f"Maximum semester load {actual}"
            unit = "credits"
        elif constraint.kind == CreditConstraintKind.MIN_DURATION_YEARS:
            actual = duration_years
            passed = actual >= constraint.value
            expected = f">= {constraint.value}"
            subject = f"Duration {actual}"
            unit = "years"
        elif constraint.kind == CreditConstraintKind.MAX_DURATION_YEARS:
            actual = duration_years
            passed = actual <= constraint.value
            expected = f"<= {constraint.value}"
            subject = f"Duration {actual}"
            unit = "years"
        elif constraint.kind == CreditConstraintKind.MIN_SEMESTERS:
            actual = Decimal(semester_count)
            passed = actual >= constraint.value
            expected = f">= {constraint.value}"
            subject = f"Semesters {semester_count}"
            unit = "semesters"
        else:
            actual = Decimal(semester_count)
            passed = actual <= constraint.value
            expected = f"<= {constraint.value}"
            subject = f"Semesters {semester_count}"
            unit = "semesters"

        checks.append(
            {
                "kind": constraint.kind.value,
                "passed": passed,
                "actual": str(actual),
                "expected": expected,
                "message": f"{subject} {unit}; source rule requires {expected}.",
                "rule_id": str(constraint.rule_id),
                "document_id": str(constraint.document_id),
                "document_title": constraint.document_title,
                "clause": constraint.clause,
                "page_number": constraint.page_number,
                "version": constraint.version,
            }
        )

    any_failed = any(not check["passed"] for check in checks)
    has_regulatory_constraints = bool(constraints)
    result_status = "failed" if any_failed else "passed" if has_regulatory_constraints else "incomplete"
    if not has_regulatory_constraints:
        checks.append(
            {
                "kind": None,
                "passed": False,
                "actual": None,
                "expected": "At least one applicable verified credit constraint",
                "message": "No applicable verified regulatory credit constraints are configured; this result cannot establish compliance.",
                "rule_id": None,
                "document_id": None,
                "document_title": None,
                "clause": None,
                "page_number": None,
                "version": None,
            }
        )
    return result_status, total_credits, checks
