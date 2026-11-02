"""Add immutable manual curriculum structure drafts.

Revision ID: 0012_curriculum_designer
Revises: 0011_course_library
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_curriculum_designer"
down_revision = "0011_course_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "curriculum_structures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("programme_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_curriculum_structures_programme_id", "curriculum_structures", ["programme_id"])
    op.create_index("ix_curriculum_structures_programme_updated", "curriculum_structures", ["programme_id", "updated_at"])
    op.create_table(
        "curriculum_structure_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("structure_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", json_type, nullable=False),
        sa.Column("validation", json_type, nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["structure_id"], ["curriculum_structures.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("structure_id", "version_number", name="uq_structure_version"),
    )
    op.create_index("ix_curriculum_structure_versions_structure_id", "curriculum_structure_versions", ["structure_id"])


def downgrade() -> None:
    op.drop_index("ix_curriculum_structure_versions_structure_id", table_name="curriculum_structure_versions")
    op.drop_table("curriculum_structure_versions")
    op.drop_index("ix_curriculum_structures_programme_updated", table_name="curriculum_structures")
    op.drop_index("ix_curriculum_structures_programme_id", table_name="curriculum_structures")
    op.drop_table("curriculum_structures")
