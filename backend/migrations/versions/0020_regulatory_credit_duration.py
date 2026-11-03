"""Store credit-table values by undergraduate degree duration."""

from alembic import op
import sqlalchemy as sa

revision = "0020_regulatory_credit_duration"
down_revision = "0019_reg_course_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "regulatory_rules",
        sa.Column("programme_duration_years", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_regulatory_rules_programme_duration_years",
        "regulatory_rules",
        ["programme_duration_years"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_regulatory_rules_programme_duration_years",
        table_name="regulatory_rules",
    )
    op.drop_column("regulatory_rules", "programme_duration_years")
