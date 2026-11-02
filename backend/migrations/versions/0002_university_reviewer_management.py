"""Add university profile fields and one-reviewer-per-university constraint.

Revision ID: 0002_university_reviewers
Revises: 0001_phase1
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_university_reviewers"
down_revision = "0001_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("universities", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("universities", sa.Column("contact_person", sa.String(length=160), nullable=True))
    op.add_column("universities", sa.Column("contact_email", sa.String(length=320), nullable=True))
    op.add_column("universities", sa.Column("phone_number", sa.String(length=32), nullable=True))
    op.add_column("universities", sa.Column("logo_url", sa.String(length=2048), nullable=True))
    op.create_index(
        "uq_users_reviewer_university",
        "users",
        ["university_id"],
        unique=True,
        sqlite_where=sa.text("role = 'reviewer' AND university_id IS NOT NULL"),
        postgresql_where=sa.text("role = 'reviewer' AND university_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_reviewer_university", table_name="users")
    op.drop_column("universities", "logo_url")
    op.drop_column("universities", "phone_number")
    op.drop_column("universities", "contact_email")
    op.drop_column("universities", "contact_person")
    op.drop_column("universities", "address")
