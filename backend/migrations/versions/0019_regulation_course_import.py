"""Track courses imported from regulation documents."""

from alembic import op
import sqlalchemy as sa

revision = "0019_reg_course_import"
down_revision = "0018_expand_credit_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "courses",
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_courses_source_document_id",
        "courses",
        "regulatory_documents",
        ["source_document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_courses_source_document_id",
        "courses",
        ["source_document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_courses_source_document_id", table_name="courses")
    op.drop_constraint("fk_courses_source_document_id", "courses", type_="foreignkey")
    op.drop_column("courses", "source_document_id")
