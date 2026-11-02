"""Add reviewer usernames derived from university codes.

Revision ID: 0003_reviewer_username
Revises: 0002_university_reviewers
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_reviewer_username"
down_revision = "0002_university_reviewers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.execute(
        sa.text(
            "UPDATE users SET username = "
            "(SELECT universities.code FROM universities WHERE universities.id = users.university_id) "
            "WHERE users.role = 'reviewer' AND users.university_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
