"""Add curriculum library, version snapshots, and reviewer publishing.

Revision ID: 0007_curriculum_library
Revises: 0006_curriculum_generation
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_curriculum_library"
down_revision = "0006_curriculum_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "curricula",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("programme_id", sa.Uuid(), nullable=False),
        sa.Column("generation_job_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_version_number", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["generation_job_id"], ["generation_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_job_id", name="uq_curricula_generation_job"),
    )
    op.create_index("ix_curricula_programme_id", "curricula", ["programme_id"])
    op.create_index("ix_curricula_programme_updated", "curricula", ["programme_id", "updated_at"])

    op.create_table(
        "curriculum_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", json_type, nullable=False),
        sa.Column("regulatory_references", json_type, nullable=False),
        sa.Column("validation_status", sa.String(length=20), nullable=False),
        sa.Column("validation_checks", json_type, nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["curriculum_id"], ["curricula.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("curriculum_id", "version_number", name="uq_curriculum_version_number"),
    )
    op.create_index("ix_curriculum_versions_curriculum_id", "curriculum_versions", ["curriculum_id"])
    op.create_index(
        "ix_curriculum_versions_curriculum_created",
        "curriculum_versions",
        ["curriculum_id", "created_at"],
    )

    op.create_table(
        "curriculum_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("university_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["curriculum_id"], ["curricula.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["curriculum_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "curriculum_id",
            "version_id",
            "reviewer_id",
            name="uq_curriculum_assignment_reviewer_version",
        ),
    )
    op.create_index("ix_curriculum_assignments_curriculum_id", "curriculum_assignments", ["curriculum_id"])
    op.create_index("ix_curriculum_assignments_version_id", "curriculum_assignments", ["version_id"])
    op.create_index("ix_curriculum_assignments_university_id", "curriculum_assignments", ["university_id"])
    op.create_index("ix_curriculum_assignments_reviewer_id", "curriculum_assignments", ["reviewer_id"])
    op.create_index(
        "ix_curriculum_assignments_reviewer_status",
        "curriculum_assignments",
        ["reviewer_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_curriculum_assignments_reviewer_status", table_name="curriculum_assignments")
    op.drop_index("ix_curriculum_assignments_reviewer_id", table_name="curriculum_assignments")
    op.drop_index("ix_curriculum_assignments_university_id", table_name="curriculum_assignments")
    op.drop_index("ix_curriculum_assignments_version_id", table_name="curriculum_assignments")
    op.drop_index("ix_curriculum_assignments_curriculum_id", table_name="curriculum_assignments")
    op.drop_table("curriculum_assignments")
    op.drop_index("ix_curriculum_versions_curriculum_created", table_name="curriculum_versions")
    op.drop_index("ix_curriculum_versions_curriculum_id", table_name="curriculum_versions")
    op.drop_table("curriculum_versions")
    op.drop_index("ix_curricula_programme_updated", table_name="curricula")
    op.drop_index("ix_curricula_programme_id", table_name="curricula")
    op.drop_table("curricula")
