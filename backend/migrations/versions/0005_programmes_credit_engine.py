"""Add programmes, regulatory credit constraints, and validation history.

Revision ID: 0005_programmes
Revises: 0004_regulatory
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_programmes"
down_revision = "0004_regulatory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    constraint_type = sa.Enum(
        "min_total_credits",
        "max_total_credits",
        "min_semester_credits",
        "max_semester_credits",
        "min_duration_years",
        "max_duration_years",
        "min_semesters",
        "max_semesters",
        name="credit_constraint_kind",
    )
    level_type = sa.Enum("ug", "pg", "doctoral", "certificate", "diploma", "other", name="programme_level")
    status_type = sa.Enum("active", "inactive", name="programme_status")

    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    regulatory_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("regulatory_documents")
    }
    with op.batch_alter_table("regulatory_documents") as batch:
        if "university_id" not in regulatory_columns:
            batch.add_column(sa.Column("university_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_regulatory_documents_university_id_universities",
            "universities",
            ["university_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index("ix_regulatory_documents_university_id", "regulatory_documents", ["university_id"])

    op.create_table(
        "credit_constraints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("kind", constraint_type, nullable=False),
        sa.Column("value", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rule_id"], ["regulatory_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "kind", name="uq_credit_constraint_rule_kind"),
    )
    op.create_index("ix_credit_constraints_rule_id", "credit_constraints", ["rule_id"])
    op.create_index("ix_credit_constraints_kind", "credit_constraints", ["kind"])

    op.create_table(
        "programmes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("university_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("degree_type", sa.String(length=120), nullable=False),
        sa.Column("specialization", sa.String(length=200), nullable=True),
        sa.Column("level", level_type, nullable=False),
        sa.Column("duration_years", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("semester_count", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("qualification_level", sa.String(length=100), nullable=True),
        sa.Column("status", status_type, nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", "name", "academic_year", name="uq_programmes_university_name_year"),
    )
    op.create_index("ix_programmes_university_id", "programmes", ["university_id"])
    op.create_index("ix_programmes_university_status", "programmes", ["university_id", "status"])

    op.create_table(
        "programme_regulatory_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("programme_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["regulatory_documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("programme_id", "document_id", name="uq_programme_regulatory_mapping"),
    )
    op.create_index("ix_programme_regulatory_mappings_programme_id", "programme_regulatory_mappings", ["programme_id"])
    op.create_index("ix_programme_regulatory_mappings_document", "programme_regulatory_mappings", ["document_id"])

    op.create_table(
        "credit_validation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("programme_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("semester_credits", json_type, nullable=False),
        sa.Column("total_credits", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("checks", json_type, nullable=False),
        sa.Column("configured_constraint_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_validation_runs_programme_id", "credit_validation_runs", ["programme_id"])
    op.create_index("ix_credit_validation_runs_programme_date", "credit_validation_runs", ["programme_id", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_credit_validation_runs_programme_date", table_name="credit_validation_runs")
    op.drop_index("ix_credit_validation_runs_programme_id", table_name="credit_validation_runs")
    op.drop_table("credit_validation_runs")
    op.drop_index("ix_programme_regulatory_mappings_document", table_name="programme_regulatory_mappings")
    op.drop_index("ix_programme_regulatory_mappings_programme_id", table_name="programme_regulatory_mappings")
    op.drop_table("programme_regulatory_mappings")
    op.drop_index("ix_programmes_university_status", table_name="programmes")
    op.drop_index("ix_programmes_university_id", table_name="programmes")
    op.drop_table("programmes")
    op.drop_index("ix_credit_constraints_kind", table_name="credit_constraints")
    op.drop_index("ix_credit_constraints_rule_id", table_name="credit_constraints")
    op.drop_table("credit_constraints")
    op.drop_index("ix_regulatory_documents_university_id", table_name="regulatory_documents")
    with op.batch_alter_table("regulatory_documents") as batch:
        batch.drop_constraint("fk_regulatory_documents_university_id_universities", type_="foreignkey")
        batch.drop_column("university_id")
    if bind.dialect.name == "postgresql":
        sa.Enum(name="programme_status").drop(bind, checkfirst=True)
        sa.Enum(name="programme_level").drop(bind, checkfirst=True)
        sa.Enum(name="credit_constraint_kind").drop(bind, checkfirst=True)
