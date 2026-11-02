import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EmbeddingType(TypeDecorator[list[float]]):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(384))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: list[float] | None, dialect):
        return value

    def process_result_value(self, value: list[float] | None, dialect):
        return list(value) if value is not None else None


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"


class UniversityStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class RegulatoryCategory(str, enum.Enum):
    UGC = "ugc"
    NEP_2020 = "nep_2020"
    NCRF = "ncrf"
    NHEQF = "nheqf"
    UNIVERSITY = "university"
    OTHER = "other"


class RegulatoryDocumentStatus(str, enum.Enum):
    READY = "ready"
    ARCHIVED = "archived"


class RuleVerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CreditConstraintKind(str, enum.Enum):
    MIN_TOTAL_CREDITS = "min_total_credits"
    MAX_TOTAL_CREDITS = "max_total_credits"
    MIN_SEMESTER_CREDITS = "min_semester_credits"
    MAX_SEMESTER_CREDITS = "max_semester_credits"
    MIN_DURATION_YEARS = "min_duration_years"
    MAX_DURATION_YEARS = "max_duration_years"
    MIN_SEMESTERS = "min_semesters"
    MAX_SEMESTERS = "max_semesters"


class ProgrammeLevel(str, enum.Enum):
    UG = "ug"
    PG = "pg"
    DOCTORAL = "doctoral"
    CERTIFICATE = "certificate"
    DIPLOMA = "diploma"
    OTHER = "other"


class ProgrammeStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class University(Base):
    __tablename__ = "universities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(160), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[UniversityStatus] = mapped_column(
        Enum(UniversityStatus, name="university_status", values_callable=lambda values: [item.value for item in values]),
        default=UniversityStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    reviewers: Mapped[list["User"]] = relationship(back_populates="university")
    colleges: Mapped[list["College"]] = relationship(back_populates="university")


class College(Base):
    __tablename__ = "colleges"
    __table_args__ = (
        UniqueConstraint("university_id", "code", name="uq_colleges_university_code"),
        Index("ix_colleges_university_status", "university_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    university_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("universities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(160), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    university: Mapped[University] = relationship(back_populates="colleges")
    reviewers: Mapped[list["User"]] = relationship(back_populates="college")
    programmes: Mapped[list["Programme"]] = relationship(back_populates="college")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_username", "username", unique=True),
        Index(
            "uq_users_reviewer_university_only",
            "university_id",
            unique=True,
            sqlite_where=text("role = 'reviewer' AND university_id IS NOT NULL AND college_id IS NULL"),
            postgresql_where=text("role = 'reviewer' AND university_id IS NOT NULL AND college_id IS NULL"),
        ),
        Index(
            "uq_users_reviewer_college",
            "college_id",
            unique=True,
            sqlite_where=text("role = 'reviewer' AND college_id IS NOT NULL"),
            postgresql_where=text("role = 'reviewer' AND college_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda values: [item.value for item in values]),
        nullable=False,
    )
    university_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("universities.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    college_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("colleges.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    university: Mapped[University | None] = relationship(back_populates="reviewers")
    college: Mapped[College | None] = relationship(back_populates="reviewers")


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class RegulatoryDocument(Base):
    __tablename__ = "regulatory_documents"
    __table_args__ = (
        Index("ix_regulatory_documents_category_status", "category", "status"),
        Index("ix_regulatory_documents_source_version", "title", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[RegulatoryCategory] = mapped_column(
        Enum(RegulatoryCategory, name="regulatory_category", values_callable=lambda values: [item.value for item in values]),
        nullable=False,
    )
    issuing_authority: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    applicability: Mapped[str] = mapped_column(String(500), nullable=False)
    university_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("universities.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_warnings: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list)
    status: Mapped[RegulatoryDocumentStatus] = mapped_column(
        Enum(RegulatoryDocumentStatus, name="regulatory_document_status", values_callable=lambda values: [item.value for item in values]),
        nullable=False,
        default=RegulatoryDocumentStatus.READY,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[list["RegulatoryChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    rules: Mapped[list["RegulatoryRule"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    university: Mapped[University | None] = relationship()


class RegulatoryChunk(Base):
    __tablename__ = "regulatory_chunks"
    __table_args__ = (
        Index("ix_regulatory_chunks_document_page", "document_id", "page_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("regulatory_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingType(), nullable=False)

    document: Mapped[RegulatoryDocument] = relationship(back_populates="chunks")


class RegulatoryRule(Base):
    __tablename__ = "regulatory_rules"
    __table_args__ = (
        Index("ix_regulatory_rules_verification", "verification_status", "has_conflict"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("regulatory_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clause: Mapped[str | None] = mapped_column(String(240), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(384).with_variant(JSON(), "sqlite"),
        nullable=False,
    )
    verification_status: Mapped[RuleVerificationStatus] = mapped_column(
        Enum(RuleVerificationStatus, name="rule_verification_status", values_callable=lambda values: [item.value for item in values]),
        nullable=False,
        default=RuleVerificationStatus.PENDING,
    )
    has_conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conflict_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[RegulatoryDocument] = relationship(back_populates="rules")
    credit_constraints: Mapped[list["CreditConstraint"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )


class CreditConstraint(Base):
    __tablename__ = "credit_constraints"
    __table_args__ = (
        UniqueConstraint("rule_id", "kind", name="uq_credit_constraint_rule_kind"),
        Index("ix_credit_constraints_kind", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("regulatory_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[CreditConstraintKind] = mapped_column(
        Enum(CreditConstraintKind, name="credit_constraint_kind", values_callable=lambda values: [item.value for item in values]),
        nullable=False,
    )
    value: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    rule: Mapped[RegulatoryRule] = relationship(back_populates="credit_constraints")


class Programme(Base):
    __tablename__ = "programmes"
    __table_args__ = (
        UniqueConstraint("university_id", "name", "academic_year", name="uq_programmes_university_name_year"),
        Index("ix_programmes_university_status", "university_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    university_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("universities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    college_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("colleges.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    degree_type: Mapped[str] = mapped_column(String(120), nullable=False)
    specialization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    level: Mapped[ProgrammeLevel] = mapped_column(
        Enum(ProgrammeLevel, name="programme_level", values_callable=lambda values: [item.value for item in values]),
        nullable=False,
    )
    duration_years: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    semester_count: Mapped[int] = mapped_column(Integer, nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    qualification_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[ProgrammeStatus] = mapped_column(
        Enum(ProgrammeStatus, name="programme_status", values_callable=lambda values: [item.value for item in values]),
        default=ProgrammeStatus.ACTIVE,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    university: Mapped[University] = relationship()
    college: Mapped[College | None] = relationship(back_populates="programmes")
    regulatory_mappings: Mapped[list["ProgrammeRegulatoryMapping"]] = relationship(
        back_populates="programme", cascade="all, delete-orphan"
    )
    validations: Mapped[list["CreditValidationRun"]] = relationship(back_populates="programme")


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("course_code", name="uq_courses_course_code"),
        Index("ix_courses_category_status", "category", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    course_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    course_type: Mapped[str] = mapped_column(String(80), nullable=False, default="theory")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    objectives: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list)
    credits: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    lecture_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    tutorial_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    practical_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    prerequisites: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list)
    programme_ids: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class CurriculumStructure(Base):
    __tablename__ = "curriculum_structures"
    __table_args__ = (Index("ix_curriculum_structures_programme_updated", "programme_id", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    programme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    programme: Mapped[Programme] = relationship()
    versions: Mapped[list["CurriculumStructureVersion"]] = relationship(
        back_populates="structure", cascade="all, delete-orphan", order_by="CurriculumStructureVersion.version_number"
    )


class CurriculumStructureVersion(Base):
    __tablename__ = "curriculum_structure_versions"
    __table_args__ = (UniqueConstraint("structure_id", "version_number", name="uq_structure_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    structure_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curriculum_structures.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    validation: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    structure: Mapped[CurriculumStructure] = relationship(back_populates="versions")


class ProgrammeRegulatoryMapping(Base):
    __tablename__ = "programme_regulatory_mappings"
    __table_args__ = (
        UniqueConstraint("programme_id", "document_id", name="uq_programme_regulatory_mapping"),
        Index("ix_programme_regulatory_mappings_document", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    programme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("regulatory_documents.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    programme: Mapped[Programme] = relationship(back_populates="regulatory_mappings")
    document: Mapped[RegulatoryDocument] = relationship()


class CreditValidationRun(Base):
    __tablename__ = "credit_validation_runs"
    __table_args__ = (Index("ix_credit_validation_runs_programme_date", "programme_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    programme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    semester_credits: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    total_credits: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    checks: Mapped[list[dict]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    configured_constraint_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    programme: Mapped[Programme] = relationship(back_populates="validations")


class CurriculumGenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (Index("ix_generation_jobs_programme_created", "programme_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    programme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generating")
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    curriculum: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    regulatory_references: Mapped[list[dict]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    validation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    validation_checks: Mapped[list[dict]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    programme: Mapped[Programme] = relationship()


class CurriculumLibraryItem(Base):
    __tablename__ = "curricula"
    __table_args__ = (
        UniqueConstraint("generation_job_id", name="uq_curricula_generation_job"),
        Index("ix_curricula_programme_updated", "programme_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    programme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation_job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("generation_jobs.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    current_version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    programme: Mapped[Programme] = relationship()
    versions: Mapped[list["CurriculumVersion"]] = relationship(
        back_populates="curriculum", cascade="all, delete-orphan", order_by="CurriculumVersion.version_number"
    )


class CurriculumVersion(Base):
    __tablename__ = "curriculum_versions"
    __table_args__ = (
        UniqueConstraint("curriculum_id", "version_number", name="uq_curriculum_version_number"),
        Index("ix_curriculum_versions_curriculum_created", "curriculum_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    regulatory_references: Mapped[list[dict]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False)
    validation_checks: Mapped[list[dict]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    curriculum: Mapped[CurriculumLibraryItem] = relationship(back_populates="versions")


class CurriculumAssignment(Base):
    __tablename__ = "curriculum_assignments"
    __table_args__ = (
        UniqueConstraint("curriculum_id", "version_id", "reviewer_id", name="uq_curriculum_assignment_reviewer_version"),
        Index("ix_curriculum_assignments_reviewer_status", "reviewer_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curriculum_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    university_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("universities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    college_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("colleges.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    curriculum: Mapped[CurriculumLibraryItem] = relationship()
    version: Mapped[CurriculumVersion] = relationship()
    university: Mapped[University] = relationship()
    reviewer: Mapped[User] = relationship()
    college: Mapped[College | None] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("curriculum_assignments.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()
    assignment: Mapped[CurriculumAssignment | None] = relationship()


class ReviewComment(Base):
    __tablename__ = "review_comments"
    __table_args__ = (
        Index("ix_review_comments_assignment_status", "assignment_id", "status"),
        Index("ix_review_comments_version", "version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curriculum_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curriculum_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    section_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    is_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    assignment: Mapped[CurriculumAssignment] = relationship()
    version: Mapped[CurriculumVersion] = relationship()
    author: Mapped[User] = relationship()
    replies: Mapped[list["CommentReply"]] = relationship(
        back_populates="comment", cascade="all, delete-orphan", order_by="CommentReply.created_at"
    )


class CommentReply(Base):
    __tablename__ = "comment_replies"
    __table_args__ = (Index("ix_comment_replies_comment_created", "comment_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    comment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("review_comments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    comment: Mapped[ReviewComment] = relationship(back_populates="replies")
    author: Mapped[User] = relationship()


class ReviewDocument(Base):
    __tablename__ = "review_documents"
    __table_args__ = (
        Index("ix_review_documents_assignment_created", "assignment_id", "created_at"),
        Index("ix_review_documents_version", "version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curriculum_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curriculum_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    related_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("review_comments.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    assignment: Mapped[CurriculumAssignment] = relationship()
    version: Mapped[CurriculumVersion] = relationship()
    comment: Mapped[ReviewComment | None] = relationship()
    uploader: Mapped[User] = relationship()


class ReviewHistory(Base):
    __tablename__ = "review_history"
    __table_args__ = (
        Index("ix_review_history_assignment_created", "assignment_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curriculum_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("curriculum_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    assignment: Mapped[CurriculumAssignment] = relationship()
    version: Mapped[CurriculumVersion] = relationship()
    actor: Mapped[User] = relationship()
