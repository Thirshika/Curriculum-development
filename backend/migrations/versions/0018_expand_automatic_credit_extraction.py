"""Recognize additional category credit totals in existing regulations."""

from alembic import op
import sqlalchemy as sa

from app.regulatory import extract_credit_rules

revision = "0018_expand_credit_rules"
down_revision = "0017_auto_credit_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    rules = sa.Table("regulatory_rules", metadata, autoload_with=bind)
    rows = bind.execute(
        sa.select(
            rules.c.id,
            rules.c.text,
        ).where(rules.c.rule_type.is_(None), rules.c.value.is_(None))
    ).mappings()

    for rule in rows:
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
    # Keep extracted values; deleting them would undo data already used by the credit tables.
    pass
