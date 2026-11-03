"""Backfill structured credit values for existing regulations."""

import re

from alembic import op
import sqlalchemy as sa

from app.regulatory import extract_credit_rules

revision = "0017_auto_credit_rules"
down_revision = "0016_regulatory_flow"
branch_labels = None
depends_on = None

YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
UG_PATTERN = re.compile(r"\b(?:undergraduate|UG)\b", re.IGNORECASE)
PG_PATTERN = re.compile(r"\b(?:postgraduate|PG)\b", re.IGNORECASE)


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    documents = sa.Table("regulatory_documents", metadata, autoload_with=bind)
    rules = sa.Table("regulatory_rules", metadata, autoload_with=bind)

    document_rows = bind.execute(
        sa.select(
            documents.c.id,
            documents.c.title,
            documents.c.applicability,
            documents.c.year,
            documents.c.programme_level,
        )
    ).mappings()
    for document in document_rows:
        title = document["title"] or ""
        updates = {}
        if document["year"] is None:
            year_match = YEAR_PATTERN.search(title)
            if year_match:
                updates["year"] = int(year_match.group())
        if document["programme_level"] is None:
            if UG_PATTERN.search(title):
                updates["programme_level"] = "ug"
            elif PG_PATTERN.search(title):
                updates["programme_level"] = "pg"
        if updates:
            bind.execute(
                documents.update()
                .where(documents.c.id == document["id"])
                .values(**updates)
            )

    rule_rows = bind.execute(
        sa.select(
            rules.c.id,
            rules.c.text,
            rules.c.rule_type,
            rules.c.value,
        ).where(rules.c.rule_type.is_(None), rules.c.value.is_(None))
    ).mappings()
    for rule in rule_rows:
        extracted = extract_credit_rules([rule["text"] or ""])
        credit_rule = next(
            (item for item in extracted if item["rule_type"] != "other" and item["value"] is not None),
            None,
        )
        if credit_rule is None:
            continue
        bind.execute(
            rules.update()
            .where(rules.c.id == rule["id"])
            .values(
                rule_type=credit_rule["rule_type"],
                category=credit_rule["category"],
                semester=credit_rule["semester"],
                value=credit_rule["value"],
            )
        )


def downgrade() -> None:
    # Keep backfilled metadata; dropping it would discard user-visible extracted data.
    pass
