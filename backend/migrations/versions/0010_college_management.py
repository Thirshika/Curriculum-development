"""Add colleges and optional college-scoped reviewer accounts.

Revision ID: 0010_college_management
Revises: 0009_review_workflow
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_college_management"
down_revision = "0009_review_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "colleges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("university_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("district", sa.String(length=120), nullable=True),
        sa.Column("contact_person", sa.String(length=160), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", "code", name="uq_colleges_university_code"),
    )
    op.create_index("ix_colleges_university_id", "colleges", ["university_id"])
    op.create_index("ix_colleges_university_status", "colleges", ["university_id", "status"])
    op.add_column("users", sa.Column("college_id", sa.Uuid(), nullable=True))
    with op.batch_alter_table("users") as batch:
        batch.create_foreign_key(
            "fk_users_college_id_colleges", "colleges", ["college_id"], ["id"], ondelete="RESTRICT"
        )
    op.create_index("ix_users_college_id", "users", ["college_id"])
    op.drop_index("uq_users_reviewer_university", table_name="users")
    op.create_index(
        "uq_users_reviewer_university_only",
        "users",
        ["university_id"],
        unique=True,
        sqlite_where=sa.text("role = 'reviewer' AND university_id IS NOT NULL AND college_id IS NULL"),
        postgresql_where=sa.text("role = 'reviewer' AND university_id IS NOT NULL AND college_id IS NULL"),
    )
    op.create_index(
        "uq_users_reviewer_college",
        "users",
        ["college_id"],
        unique=True,
        sqlite_where=sa.text("role = 'reviewer' AND college_id IS NOT NULL"),
        postgresql_where=sa.text("role = 'reviewer' AND college_id IS NOT NULL"),
    )
    op.add_column("curriculum_assignments", sa.Column("college_id", sa.Uuid(), nullable=True))
    with op.batch_alter_table("curriculum_assignments") as batch:
        batch.create_foreign_key(
            "fk_curriculum_assignments_college_id_colleges",
            "colleges",
            ["college_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index("ix_curriculum_assignments_college_id", "curriculum_assignments", ["college_id"])


def downgrade() -> None:
    op.drop_index("ix_curriculum_assignments_college_id", table_name="curriculum_assignments")
    with op.batch_alter_table("curriculum_assignments") as batch:
        batch.drop_constraint("fk_curriculum_assignments_college_id_colleges", type_="foreignkey")
    op.drop_column("curriculum_assignments", "college_id")
    op.drop_index("uq_users_reviewer_college", table_name="users")
    op.drop_index("uq_users_reviewer_university_only", table_name="users")
    op.create_index(
        "uq_users_reviewer_university",
        "users",
        ["university_id"],
        unique=True,
        sqlite_where=sa.text("role = 'reviewer' AND university_id IS NOT NULL"),
        postgresql_where=sa.text("role = 'reviewer' AND university_id IS NOT NULL"),
    )
    op.drop_index("ix_users_college_id", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_college_id_colleges", type_="foreignkey")
    op.drop_column("users", "college_id")
    op.drop_index("ix_colleges_university_status", table_name="colleges")
    op.drop_index("ix_colleges_university_id", table_name="colleges")
    op.drop_table("colleges")
