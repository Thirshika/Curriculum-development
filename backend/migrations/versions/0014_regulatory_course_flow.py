"""Support approved credit rules, manual limits, and semester course data.

Revision ID: 0014_regulatory_course_flow
Revises: 0013_programme_college_scope
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0014_regulatory_course_flow"
down_revision = "0013_programme_college_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("regulatory_documents") as batch:
        batch.add_column(sa.Column("year", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("programme_level", sa.String(length=2), nullable=True))

    embedding_type = sa.JSON().with_variant(Vector(384), "postgresql")
    with op.batch_alter_table("regulatory_rules") as batch:
        batch.add_column(sa.Column("rule_type", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("category", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("semester", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("value", sa.Numeric(precision=10, scale=2), nullable=True))
        batch.alter_column("embedding", existing_type=embedding_type, nullable=True)

    with op.batch_alter_table("courses") as batch:
        batch.add_column(sa.Column("semester", sa.Integer(), nullable=False, server_default="1"))

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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("programme_level", "scope_key", "limit_type", name="uq_credit_table_override_scope"),
    )
    op.create_index("ix_credit_table_overrides_level", "credit_table_overrides", ["programme_level"])


def downgrade() -> None:
    op.drop_index("ix_credit_table_overrides_level", table_name="credit_table_overrides")
    op.drop_table("credit_table_overrides")
    with op.batch_alter_table("courses") as batch:
        batch.drop_column("semester")
    embedding_type = sa.JSON().with_variant(Vector(384), "postgresql")
    with op.batch_alter_table("regulatory_rules") as batch:
        batch.alter_column("embedding", existing_type=embedding_type, nullable=False)
        batch.drop_column("value")
        batch.drop_column("semester")
        batch.drop_column("category")
        batch.drop_column("rule_type")
    with op.batch_alter_table("regulatory_documents") as batch:
        batch.drop_column("programme_level")
        batch.drop_column("year")
