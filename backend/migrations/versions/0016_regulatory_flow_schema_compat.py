"""Ensure regulatory credit-flow columns exist on upgraded databases.

Some databases were stamped at 0015_course_candidates before the regulatory
credit-flow schema was included in this migration checkout.
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_regulatory_flow"
down_revision = "0015_course_candidates"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> dict[str, dict]:
    return {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def upgrade() -> None:
    document_columns = _columns("regulatory_documents")
    if "year" not in document_columns:
        op.add_column("regulatory_documents", sa.Column("year", sa.Integer(), nullable=True))
    if "programme_level" not in document_columns:
        op.add_column(
            "regulatory_documents",
            sa.Column("programme_level", sa.String(length=2), nullable=True),
        )

    rule_columns = _columns("regulatory_rules")
    for name, column_type in (
        ("rule_type", sa.String(length=40)),
        ("category", sa.String(length=100)),
        ("semester", sa.Integer()),
        ("value", sa.Numeric(precision=10, scale=2)),
    ):
        if name not in rule_columns:
            op.add_column(
                "regulatory_rules",
                sa.Column(name, column_type, nullable=True),
            )
    embedding = rule_columns.get("embedding")
    if embedding is not None and not embedding["nullable"]:
        with op.batch_alter_table("regulatory_rules") as batch:
            batch.alter_column(
                "embedding",
                existing_type=embedding["type"],
                nullable=True,
            )

    course_columns = _columns("courses")
    if "semester" not in course_columns:
        op.add_column(
            "courses",
            sa.Column("semester", sa.Integer(), nullable=False, server_default="1"),
        )

    inspector = sa.inspect(op.get_bind())
    if "credit_table_overrides" not in inspector.get_table_names():
        op.create_table(
            "credit_table_overrides",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("programme_level", sa.String(length=2), nullable=False),
            sa.Column("scope_type", sa.String(length=20), nullable=False),
            sa.Column("scope_key", sa.String(length=120), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=True),
            sa.Column("semester", sa.Integer(), nullable=True),
            sa.Column("limit_type", sa.String(length=30), nullable=False),
            sa.Column("value", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column("updated_by", sa.Uuid(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["updated_by"],
                ["users.id"],
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "programme_level",
                "scope_key",
                "limit_type",
                name="uq_credit_table_override_scope",
            ),
        )

    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("credit_table_overrides")
    }
    if "ix_credit_table_overrides_level" not in indexes:
        op.create_index(
            "ix_credit_table_overrides_level",
            "credit_table_overrides",
            ["programme_level"],
        )


def downgrade() -> None:
    op.drop_index("ix_credit_table_overrides_level", table_name="credit_table_overrides")
    op.drop_table("credit_table_overrides")
    op.drop_column("courses", "semester")
    op.drop_column("regulatory_rules", "value")
    op.drop_column("regulatory_rules", "semester")
    op.drop_column("regulatory_rules", "category")
    op.drop_column("regulatory_rules", "rule_type")
    with op.batch_alter_table("regulatory_rules") as batch:
        batch.alter_column("embedding", nullable=False)
    op.drop_column("regulatory_documents", "programme_level")
    op.drop_column("regulatory_documents", "year")
