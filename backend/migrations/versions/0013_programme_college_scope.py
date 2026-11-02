"""Associate programmes with their owning college when known.

Revision ID: 0013_programme_college_scope
Revises: 0012_curriculum_designer
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_programme_college_scope"
down_revision = "0012_curriculum_designer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("programmes") as batch_op:
        batch_op.add_column(sa.Column("college_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_programmes_college_id_colleges",
            "colleges",
            ["college_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_programmes_college_id", "programmes", ["college_id"])


def downgrade() -> None:
    op.drop_index("ix_programmes_college_id", table_name="programmes")
    with op.batch_alter_table("programmes") as batch_op:
        batch_op.drop_constraint("fk_programmes_college_id_colleges", type_="foreignkey")
        batch_op.drop_column("college_id")
