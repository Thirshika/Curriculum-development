"""Preserve regulation-derived course candidates."""

from alembic import op
import sqlalchemy as sa

revision = "0015_course_candidates"
down_revision = "0014_regulatory_course_flow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "regulatory_course_candidates" in inspector.get_table_names():
        return

    op.create_table(
        "regulatory_course_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("course_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("course_type", sa.String(length=80), nullable=False),
        sa.Column("credits", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("lecture_hours", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("tutorial_hours", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("practical_hours", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("imported_course_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["regulatory_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["imported_course_id"],
            ["courses.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "course_code",
            name="uq_regulatory_course_candidate_code",
        ),
    )
    op.create_index(
        "ix_regulatory_course_candidates_document_id",
        "regulatory_course_candidates",
        ["document_id"],
    )
    op.create_index(
        "ix_regulatory_course_candidates_status",
        "regulatory_course_candidates",
        ["status"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "regulatory_course_candidates" not in inspector.get_table_names():
        return
    op.drop_index(
        "ix_regulatory_course_candidates_status",
        table_name="regulatory_course_candidates",
    )
    op.drop_index(
        "ix_regulatory_course_candidates_document_id",
        table_name="regulatory_course_candidates",
    )
    op.drop_table("regulatory_course_candidates")
