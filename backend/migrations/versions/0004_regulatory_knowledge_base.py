"""Create regulatory documents, searchable chunks, and reviewable rules.

Revision ID: 0004_regulatory
Revises: 0003_reviewer_username
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0004_regulatory"
down_revision = "0003_reviewer_username"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    category_type = sa.Enum("ugc", "nep_2020", "ncrf", "nheqf", "university", "other", name="regulatory_category")
    document_status_type = sa.Enum("ready", "archived", name="regulatory_document_status")
    verification_type = sa.Enum("pending", "verified", "rejected", name="rule_verification_status")
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    embedding_type = sa.JSON().with_variant(Vector(384), "postgresql")
    op.create_table(
        "regulatory_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("category", category_type, nullable=False),
        sa.Column("issuing_authority", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("applicability", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("extraction_warnings", json_type, nullable=False),
        sa.Column("status", document_status_type, nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_regulatory_documents_category_status", "regulatory_documents", ["category", "status"])
    op.create_index("ix_regulatory_documents_source_version", "regulatory_documents", ["title", "version"])
    op.create_index("ix_regulatory_documents_sha256", "regulatory_documents", ["sha256"])
    op.create_index("ix_regulatory_documents_uploaded_by", "regulatory_documents", ["uploaded_by"])

    op.create_table(
        "regulatory_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["regulatory_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regulatory_chunks_document_id", "regulatory_chunks", ["document_id"])
    op.create_index("ix_regulatory_chunks_document_page", "regulatory_chunks", ["document_id", "page_number"])

    op.create_table(
        "regulatory_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("clause", sa.String(length=240), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.Column("verification_status", verification_type, nullable=False),
        sa.Column("has_conflict", sa.Boolean(), nullable=False),
        sa.Column("conflict_note", sa.Text(), nullable=True),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["regulatory_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regulatory_rules_document_id", "regulatory_rules", ["document_id"])
    op.create_index("ix_regulatory_rules_verification", "regulatory_rules", ["verification_status", "has_conflict"])


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_regulatory_rules_verification", table_name="regulatory_rules")
    op.drop_index("ix_regulatory_rules_document_id", table_name="regulatory_rules")
    op.drop_table("regulatory_rules")
    op.drop_index("ix_regulatory_chunks_document_page", table_name="regulatory_chunks")
    op.drop_index("ix_regulatory_chunks_document_id", table_name="regulatory_chunks")
    op.drop_table("regulatory_chunks")
    op.drop_index("ix_regulatory_documents_uploaded_by", table_name="regulatory_documents")
    op.drop_index("ix_regulatory_documents_sha256", table_name="regulatory_documents")
    op.drop_index("ix_regulatory_documents_source_version", table_name="regulatory_documents")
    op.drop_index("ix_regulatory_documents_category_status", table_name="regulatory_documents")
    op.drop_table("regulatory_documents")
    if bind.dialect.name == "postgresql":
        sa.Enum(name="rule_verification_status").drop(bind, checkfirst=True)
        sa.Enum(name="regulatory_document_status").drop(bind, checkfirst=True)
        sa.Enum(name="regulatory_category").drop(bind, checkfirst=True)
