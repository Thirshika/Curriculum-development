"""Add reviewer comments, documents, replies, and review history.

Revision ID: 0009_review_workflow
Revises: 0008_publication_notifications
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_review_workflow"
down_revision = "0008_publication_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "review_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("section_path", sa.String(length=500), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("is_submitted", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["curriculum_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["curriculum_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_comments_assignment_id", "review_comments", ["assignment_id"])
    op.create_index("ix_review_comments_assignment_status", "review_comments", ["assignment_id", "status"])
    op.create_index("ix_review_comments_created_by", "review_comments", ["created_by"])
    op.create_index("ix_review_comments_version_id", "review_comments", ["version_id"])
    op.create_index("ix_review_comments_version", "review_comments", ["version_id"])

    op.create_table(
        "comment_replies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["comment_id"], ["review_comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comment_replies_author_id", "comment_replies", ["author_id"])
    op.create_index("ix_comment_replies_comment_id", "comment_replies", ["comment_id"])
    op.create_index("ix_comment_replies_comment_created", "comment_replies", ["comment_id", "created_at"])

    op.create_table(
        "review_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("related_comment_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["curriculum_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_comment_id"], ["review_comments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["curriculum_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_review_documents_assignment_id", "review_documents", ["assignment_id"])
    op.create_index("ix_review_documents_assignment_created", "review_documents", ["assignment_id", "created_at"])
    op.create_index("ix_review_documents_sha256", "review_documents", ["sha256"])
    op.create_index("ix_review_documents_uploaded_by", "review_documents", ["uploaded_by"])
    op.create_index("ix_review_documents_version_id", "review_documents", ["version_id"])
    op.create_index("ix_review_documents_version", "review_documents", ["version_id"])

    op.create_table(
        "review_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("details", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assignment_id"], ["curriculum_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["curriculum_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_history_actor_id", "review_history", ["actor_id"])
    op.create_index("ix_review_history_assignment_id", "review_history", ["assignment_id"])
    op.create_index("ix_review_history_assignment_created", "review_history", ["assignment_id", "created_at"])
    op.create_index("ix_review_history_version_id", "review_history", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_review_history_version_id", table_name="review_history")
    op.drop_index("ix_review_history_assignment_created", table_name="review_history")
    op.drop_index("ix_review_history_assignment_id", table_name="review_history")
    op.drop_index("ix_review_history_actor_id", table_name="review_history")
    op.drop_table("review_history")
    op.drop_index("ix_review_documents_version", table_name="review_documents")
    op.drop_index("ix_review_documents_version_id", table_name="review_documents")
    op.drop_index("ix_review_documents_uploaded_by", table_name="review_documents")
    op.drop_index("ix_review_documents_sha256", table_name="review_documents")
    op.drop_index("ix_review_documents_assignment_created", table_name="review_documents")
    op.drop_index("ix_review_documents_assignment_id", table_name="review_documents")
    op.drop_table("review_documents")
    op.drop_index("ix_comment_replies_comment_created", table_name="comment_replies")
    op.drop_index("ix_comment_replies_comment_id", table_name="comment_replies")
    op.drop_index("ix_comment_replies_author_id", table_name="comment_replies")
    op.drop_table("comment_replies")
    op.drop_index("ix_review_comments_version", table_name="review_comments")
    op.drop_index("ix_review_comments_version_id", table_name="review_comments")
    op.drop_index("ix_review_comments_created_by", table_name="review_comments")
    op.drop_index("ix_review_comments_assignment_status", table_name="review_comments")
    op.drop_index("ix_review_comments_assignment_id", table_name="review_comments")
    op.drop_table("review_comments")
