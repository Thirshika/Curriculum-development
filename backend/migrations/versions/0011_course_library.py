"""Add reusable course catalogue.

Revision ID: 0011_course_library
Revises: 0010_college_management
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_course_library"
down_revision = "0010_college_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("course_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("objectives", json_type, nullable=False),
        sa.Column("credits", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("lecture_hours", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("tutorial_hours", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("practical_hours", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("prerequisites", json_type, nullable=False),
        sa.Column("programme_ids", json_type, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_code", name="uq_courses_course_code"),
    )
    op.create_index("ix_courses_category_status", "courses", ["category", "status"])


def downgrade() -> None:
    op.drop_index("ix_courses_category_status", table_name="courses")
    op.drop_table("courses")
