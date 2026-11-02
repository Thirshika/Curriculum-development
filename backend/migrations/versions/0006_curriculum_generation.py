"""Add persistent curriculum generation jobs.

Revision ID: 0006_curriculum_generation
Revises: 0005_programmes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_curriculum_generation"
down_revision = "0005_programmes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("programme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("curriculum", json_type, nullable=True),
        sa.Column("regulatory_references", json_type, nullable=False),
        sa.Column("validation_status", sa.String(length=20), nullable=True),
        sa.Column("validation_checks", json_type, nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generation_jobs_programme_id", "generation_jobs", ["programme_id"])
    op.create_index(
        "ix_generation_jobs_programme_created",
        "generation_jobs",
        ["programme_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_generation_jobs_programme_created", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_programme_id", table_name="generation_jobs")
    op.drop_table("generation_jobs")
