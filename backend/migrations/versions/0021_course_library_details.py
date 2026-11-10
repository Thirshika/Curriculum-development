"""Extend existing programme and course records for the course library."""

import json
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0021_course_library_details"
down_revision = "0020_regulatory_credit_duration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("programmes", sa.Column("catalogue_course_name", sa.String(length=240), nullable=True))
    op.add_column("programmes", sa.Column("catalogue_course_code", sa.String(length=32), nullable=True))
    op.add_column("programmes", sa.Column("faculty_school", sa.String(length=200), nullable=True))
    op.add_column("programmes", sa.Column("department", sa.String(length=200), nullable=True))
    op.add_column("programmes", sa.Column("course_description", sa.Text(), nullable=True))
    op.add_column("programmes", sa.Column("regulation_year", sa.String(length=20), nullable=True))
    op.add_column("programmes", sa.Column("effective_from", sa.Date(), nullable=True))
    op.add_column("programmes", sa.Column("effective_until", sa.Date(), nullable=True))
    op.add_column("programmes", sa.Column("catalogue_status", sa.String(length=20), nullable=True))
    op.create_index(
        "uq_programmes_university_catalogue_course_code",
        "programmes",
        ["university_id", "catalogue_course_code"],
        unique=True,
    )

    with op.batch_alter_table("courses") as batch:
        batch.add_column(sa.Column("programme_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("internal_marks", sa.Numeric(precision=8, scale=2), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("external_marks", sa.Numeric(precision=8, scale=2), nullable=False, server_default="0")
        )
        batch.create_foreign_key(
            "fk_courses_programme_id_programmes",
            "programmes",
            ["programme_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_courses_programme_id", "courses", ["programme_id"])

    bind = op.get_bind()
    courses = sa.Table("courses", sa.MetaData(), autoload_with=bind)
    programmes = sa.Table("programmes", sa.MetaData(), autoload_with=bind)
    for course_id, programme_ids in bind.execute(
        sa.select(courses.c.id, courses.c.programme_ids).where(courses.c.programme_ids.is_not(None))
    ):
        if isinstance(programme_ids, str):
            try:
                programme_ids = json.loads(programme_ids)
            except json.JSONDecodeError:
                continue
        if not isinstance(programme_ids, list) or len(programme_ids) != 1:
            continue
        try:
            programme_id = uuid.UUID(str(programme_ids[0]))
        except (ValueError, TypeError, AttributeError):
            continue
        exists = bind.execute(
            sa.select(programmes.c.id).where(programmes.c.id == programme_id)
        ).first()
        if exists:
            bind.execute(
                courses.update()
                .where(courses.c.id == course_id)
                .values(programme_id=programme_id)
            )


def downgrade() -> None:
    op.drop_index("ix_courses_programme_id", table_name="courses")
    with op.batch_alter_table("courses") as batch:
        batch.drop_constraint("fk_courses_programme_id_programmes", type_="foreignkey")
        batch.drop_column("external_marks")
        batch.drop_column("internal_marks")
        batch.drop_column("programme_id")
    op.drop_index("uq_programmes_university_catalogue_course_code", table_name="programmes")
    op.drop_column("programmes", "catalogue_status")
    op.drop_column("programmes", "effective_until")
    op.drop_column("programmes", "effective_from")
    op.drop_column("programmes", "regulation_year")
    op.drop_column("programmes", "course_description")
    op.drop_column("programmes", "department")
    op.drop_column("programmes", "faculty_school")
    op.drop_column("programmes", "catalogue_course_code")
    op.drop_column("programmes", "catalogue_course_name")
