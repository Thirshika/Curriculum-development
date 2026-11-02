import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class Role(str, Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    username: str | None = None
    full_name: str
    role: Role
    university_id: uuid.UUID | None
    university_name: str | None = None
    college_id: uuid.UUID | None = None
    college_name: str | None = None
    must_change_password: bool

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=2, max_length=64)
    password: str
    expected_role: Role | None = None

    @model_validator(mode="after")
    def require_one_login_identifier(self):
        if bool(self.email) == bool(self.username):
            raise ValueError("Provide either an email address or a username")
        if self.username:
            self.username = self.username.strip()
        return self


class ReviewerSignupRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=128)
    university_id: uuid.UUID | None = None
    college_id: uuid.UUID | None = None
    new_university_name: str | None = Field(default=None, min_length=2, max_length=200)
    new_university_code: str | None = Field(
        default=None, min_length=2, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
    )

    @field_validator("email")
    @classmethod
    def normalize_signup_email(cls, value: EmailStr) -> EmailStr:
        return value.lower()

    @field_validator("full_name", "new_university_name", "new_university_code", mode="before")
    @classmethod
    def strip_signup_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("new_university_code")
    @classmethod
    def normalize_signup_university_code(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def validate_university_selection(self):
        existing_university = self.university_id is not None
        new_university = self.new_university_name is not None or self.new_university_code is not None
        if existing_university == new_university:
            raise ValueError("Choose an existing university or provide a new university name and code")
        if new_university and (not self.new_university_name or not self.new_university_code or self.college_id):
            raise ValueError("New university signups require a university name and code and cannot select a college")
        if existing_university and (self.new_university_name or self.new_university_code):
            raise ValueError("Do not provide new university details when selecting an existing university")
        if self.password.strip() != self.password:
            raise ValueError("Password cannot start or end with whitespace")
        return self


class SignupCollegeOption(BaseModel):
    id: uuid.UUID
    name: str
    code: str


class SignupUniversityOption(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    university_wide_available: bool
    colleges: list[SignupCollegeOption]


class ReviewerSignupOptionsResponse(BaseModel):
    universities: list[SignupUniversityOption]


class ReviewerSignupResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class HealthResponse(BaseModel):
    status: str
    database: str


class AdminDashboardResponse(BaseModel):
    total_universities: int
    reviewer_accounts: int
    total_programmes: int
    total_curricula: int


class ReviewerDashboardResponse(BaseModel):
    university_name: str
    assigned_curricula: int
    pending_reviews: int
    under_review: int
    revision_requested: int
    approved_curricula: int


class UniversityResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None
    contact_person: str | None
    contact_email: EmailStr | None
    phone_number: str | None
    logo_url: str | None
    status: str
    created_at: datetime
    reviewer_id: uuid.UUID | None = None
    reviewer_name: str | None = None
    reviewer_email: EmailStr | None = None

    model_config = ConfigDict(from_attributes=True)


class UniversityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    address: str | None = Field(default=None, max_length=4000)
    contact_person: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr | None = None
    phone_number: str | None = Field(default=None, max_length=32)
    logo_url: str | None = Field(default=None, max_length=2048)

    @field_validator("name", "code", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper()

    @field_validator("contact_email")
    @classmethod
    def normalize_contact_email(cls, value: EmailStr | None) -> EmailStr | None:
        return value.lower() if value else value


class UniversityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    address: str | None = Field(default=None, max_length=4000)
    contact_person: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr | None = None
    phone_number: str | None = Field(default=None, max_length=32)
    logo_url: str | None = Field(default=None, max_length=2048)

    @field_validator("name", "contact_person", "phone_number", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("contact_email")
    @classmethod
    def normalize_contact_email(cls, value: EmailStr | None) -> EmailStr | None:
        return value.lower() if value else value


class UniversityStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(active|inactive)$")


class CollegeCreate(BaseModel):
    university_id: uuid.UUID
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    address: str | None = Field(default=None, max_length=4000)
    state: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    contact_person: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr | None = None
    phone_number: str | None = Field(default=None, max_length=32)
    website: str | None = Field(default=None, max_length=2048)

    @field_validator("name", "code", mode="before")
    @classmethod
    def strip_college_identity(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("code")
    @classmethod
    def normalize_college_code(cls, value: str) -> str:
        return value.upper()

    @field_validator("contact_email")
    @classmethod
    def normalize_college_email(cls, value: EmailStr | None) -> EmailStr | None:
        return value.lower() if value else value


class CollegeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    address: str | None = Field(default=None, max_length=4000)
    state: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    contact_person: str | None = Field(default=None, max_length=160)
    contact_email: EmailStr | None = None
    phone_number: str | None = Field(default=None, max_length=32)
    website: str | None = Field(default=None, max_length=2048)
    status: str | None = Field(default=None, pattern=r"^(active|inactive)$")


class CollegeResponse(BaseModel):
    id: uuid.UUID
    university_id: uuid.UUID
    university_name: str
    name: str
    code: str
    address: str | None
    state: str | None
    district: str | None
    contact_person: str | None
    contact_email: EmailStr | None
    phone_number: str | None
    website: str | None
    status: str
    reviewer_id: uuid.UUID | None
    reviewer_name: str | None
    reviewer_email: EmailStr | None
    programme_count: int
    assignment_count: int
    created_at: datetime


class CourseCreate(BaseModel):
    course_code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=2, max_length=100)
    course_type: str = Field(default="theory", min_length=2, max_length=80)
    description: str = Field(default="", max_length=4000)
    objectives: list[str] = Field(default_factory=list, max_length=30)
    credits: Decimal = Field(gt=0, le=Decimal("1000"), max_digits=8, decimal_places=2)
    lecture_hours: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("1000"), max_digits=6, decimal_places=2)
    tutorial_hours: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("1000"), max_digits=6, decimal_places=2)
    practical_hours: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("1000"), max_digits=6, decimal_places=2)
    prerequisites: list[str] = Field(default_factory=list, max_length=30)
    programme_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)

    @field_validator("course_code")
    @classmethod
    def normalize_course_code(cls, value: str) -> str:
        return value.upper()


class CourseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    course_type: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=4000)
    objectives: list[str] | None = Field(default=None, max_length=30)
    credits: Decimal | None = Field(default=None, gt=0, le=Decimal("1000"), max_digits=8, decimal_places=2)
    lecture_hours: Decimal | None = Field(default=None, ge=0, le=Decimal("1000"), max_digits=6, decimal_places=2)
    tutorial_hours: Decimal | None = Field(default=None, ge=0, le=Decimal("1000"), max_digits=6, decimal_places=2)
    practical_hours: Decimal | None = Field(default=None, ge=0, le=Decimal("1000"), max_digits=6, decimal_places=2)
    prerequisites: list[str] | None = Field(default=None, max_length=30)
    programme_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, pattern=r"^(active|archived)$")


class CourseResponse(BaseModel):
    id: uuid.UUID
    course_code: str
    name: str
    category: str
    course_type: str
    description: str
    objectives: list[str]
    credits: Decimal
    lecture_hours: Decimal
    tutorial_hours: Decimal
    practical_hours: Decimal
    prerequisites: list[str]
    programme_ids: list[str]
    status: str
    created_at: datetime
    updated_at: datetime


class CurriculumStructureCourse(BaseModel):
    course_id: uuid.UUID
    credits: Decimal = Field(gt=0, le=Decimal("1000"), max_digits=8, decimal_places=2)


class CurriculumStructureSemester(BaseModel):
    semester_number: int = Field(ge=1, le=24)
    courses: list[CurriculumStructureCourse] = Field(default_factory=list, max_length=50)


class CurriculumStructureContent(BaseModel):
    semesters: list[CurriculumStructureSemester] = Field(min_length=1, max_length=24)


class CurriculumStructureCreate(BaseModel):
    programme_id: uuid.UUID
    title: str = Field(min_length=2, max_length=240)
    content: CurriculumStructureContent


class CurriculumStructureUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    content: CurriculumStructureContent | None = None


class CurriculumStructureVersionResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    content: CurriculumStructureContent
    validation: dict | None
    created_at: datetime


class CurriculumStructureResponse(BaseModel):
    id: uuid.UUID
    programme_id: uuid.UUID
    programme_name: str
    university_name: str
    title: str
    current_version: int
    version: CurriculumStructureVersionResponse
    created_at: datetime
    updated_at: datetime


class ReviewerCreate(BaseModel):
    university_id: uuid.UUID
    college_id: uuid.UUID | None = None
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> EmailStr:
        return value.lower()


class ReviewerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: EmailStr | None = None
    is_active: bool | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> EmailStr | None:
        return value.lower() if value else value


class ReviewerResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    username: str
    full_name: str
    university_id: uuid.UUID
    university_name: str
    university_code: str
    college_id: uuid.UUID | None = None
    college_name: str | None = None
    is_active: bool
    must_change_password: bool
    created_at: datetime


class ReviewerProvisionedResponse(BaseModel):
    reviewer: ReviewerResponse
    temporary_password: str


class TemporaryPasswordResponse(BaseModel):
    temporary_password: str


class RegulatoryCategoryValue(str, Enum):
    UGC = "ugc"
    NEP_2020 = "nep_2020"
    NCRF = "ncrf"
    NHEQF = "nheqf"
    UNIVERSITY = "university"
    OTHER = "other"


class RegulatoryDocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    category: RegulatoryCategoryValue
    issuing_authority: str
    version: str
    effective_date: date | None
    applicability: str
    university_id: uuid.UUID | None
    university_name: str | None = None
    original_filename: str
    mime_type: str
    file_size: int
    page_count: int
    chunk_count: int
    status: str
    extraction_warnings: list[str]
    pending_rules: int
    verified_rules: int
    rejected_rules: int
    created_at: datetime
    archived_at: datetime | None


class RegulatoryTextResponse(BaseModel):
    document_id: uuid.UUID
    title: str
    extracted_text: str


class RegulatoryRuleResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    category: RegulatoryCategoryValue
    issuing_authority: str
    version: str
    effective_date: date | None
    applicability: str
    clause: str | None
    page_number: int | None
    text: str
    verification_status: str
    has_conflict: bool
    conflict_note: str | None
    verified_by: uuid.UUID | None
    verified_at: datetime | None


class RuleVerificationUpdate(BaseModel):
    verification_status: str = Field(pattern=r"^(verified|rejected)$")


class RuleConflictUpdate(BaseModel):
    has_conflict: bool
    conflict_note: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_conflict_note(self):
        if self.has_conflict and not (self.conflict_note or "").strip():
            raise ValueError("Provide a note describing the potential regulatory conflict")
        return self


class RegulatorySearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    categories: list[RegulatoryCategoryValue] | None = None
    top_k: int = Field(default=8, ge=1, le=25)


class RegulatorySearchResult(BaseModel):
    rule_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    category: RegulatoryCategoryValue
    issuing_authority: str
    version: str
    effective_date: date | None
    applicability: str
    clause: str | None
    page_number: int | None
    text: str
    similarity: float
    has_conflict: bool


class CreditConstraintKindValue(str, Enum):
    MIN_TOTAL_CREDITS = "min_total_credits"
    MAX_TOTAL_CREDITS = "max_total_credits"
    MIN_SEMESTER_CREDITS = "min_semester_credits"
    MAX_SEMESTER_CREDITS = "max_semester_credits"
    MIN_DURATION_YEARS = "min_duration_years"
    MAX_DURATION_YEARS = "max_duration_years"
    MIN_SEMESTERS = "min_semesters"
    MAX_SEMESTERS = "max_semesters"


class CreditConstraintUpsert(BaseModel):
    kind: CreditConstraintKindValue
    value: Decimal = Field(gt=0, le=Decimal("100000"), max_digits=8, decimal_places=2)


class CreditConstraintResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    kind: CreditConstraintKindValue
    value: Decimal
    rule_text: str
    clause: str | None
    page_number: int | None
    document_id: uuid.UUID
    document_title: str
    document_category: RegulatoryCategoryValue
    document_version: str
    effective_date: date | None
    applicability: str


class ProgrammeLevelValue(str, Enum):
    UG = "ug"
    PG = "pg"
    DOCTORAL = "doctoral"
    CERTIFICATE = "certificate"
    DIPLOMA = "diploma"
    OTHER = "other"


class ProgrammeStatusValue(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ProgrammeCreate(BaseModel):
    university_id: uuid.UUID
    college_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=240)
    degree_type: str = Field(min_length=2, max_length=120)
    specialization: str | None = Field(default=None, max_length=200)
    level: ProgrammeLevelValue
    duration_years: Decimal = Field(gt=0, le=Decimal("12"), max_digits=5, decimal_places=2)
    semester_count: int = Field(ge=1, le=24)
    academic_year: str = Field(pattern=r"^20\d{2}-20\d{2}$", min_length=9, max_length=9)
    qualification_level: str | None = Field(default=None, max_length=100)
    regulatory_document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    @field_validator("name", "degree_type", "specialization", "qualification_level", mode="before")
    @classmethod
    def strip_programme_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("academic_year")
    @classmethod
    def validate_academic_year_order(cls, value: str) -> str:
        start, end = (int(year) for year in value.split("-"))
        if end != start + 1:
            raise ValueError("Academic year must span consecutive years")
        return value


class ProgrammeUpdate(BaseModel):
    college_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=240)
    degree_type: str | None = Field(default=None, min_length=2, max_length=120)
    specialization: str | None = Field(default=None, max_length=200)
    level: ProgrammeLevelValue | None = None
    duration_years: Decimal | None = Field(default=None, gt=0, le=Decimal("12"), max_digits=5, decimal_places=2)
    semester_count: int | None = Field(default=None, ge=1, le=24)
    academic_year: str | None = Field(default=None, pattern=r"^20\d{2}-20\d{2}$", min_length=9, max_length=9)
    qualification_level: str | None = Field(default=None, max_length=100)
    status: ProgrammeStatusValue | None = None
    regulatory_document_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)

    @field_validator("name", "degree_type", "specialization", "qualification_level", mode="before")
    @classmethod
    def strip_programme_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("academic_year")
    @classmethod
    def validate_academic_year_order(cls, value: str | None) -> str | None:
        if value:
            start, end = (int(year) for year in value.split("-"))
            if end != start + 1:
                raise ValueError("Academic year must span consecutive years")
        return value


class ProgrammeRegulatoryResponse(BaseModel):
    document_id: uuid.UUID
    title: str
    category: RegulatoryCategoryValue
    issuing_authority: str
    version: str
    effective_date: date | None
    applicability: str
    status: str
    verified_rule_count: int
    constraints: list[CreditConstraintResponse]


class ProgrammeResponse(BaseModel):
    id: uuid.UUID
    university_id: uuid.UUID
    college_id: uuid.UUID | None
    college_name: str | None
    university_name: str
    university_code: str
    name: str
    degree_type: str
    specialization: str | None
    level: ProgrammeLevelValue
    duration_years: Decimal
    semester_count: int
    academic_year: str
    qualification_level: str | None
    status: ProgrammeStatusValue
    created_at: datetime
    updated_at: datetime
    applicable_regulations: list[ProgrammeRegulatoryResponse]


class CreditValidationRequest(BaseModel):
    semester_credits: list[Decimal] = Field(min_length=1, max_length=24)

    @field_validator("semester_credits")
    @classmethod
    def validate_semester_credits(cls, values: list[Decimal]) -> list[Decimal]:
        if any(value < 0 or value > Decimal("10000") for value in values):
            raise ValueError("Semester credits must be between 0 and 10,000")
        return values


class CreditCheckResult(BaseModel):
    kind: CreditConstraintKindValue | None
    passed: bool
    actual: Decimal | None
    expected: str
    message: str
    rule_id: uuid.UUID | None
    document_id: uuid.UUID | None
    document_title: str | None
    clause: str | None
    page_number: int | None
    version: str | None


class CreditValidationResponse(BaseModel):
    id: uuid.UUID
    programme_id: uuid.UUID
    semester_credits: list[Decimal]
    total_credits: Decimal
    status: str
    configured_constraint_count: int
    checks: list[CreditCheckResult]
    created_at: datetime


class StructuredSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CurriculumOutcome(StructuredSchema):
    code: str = Field(min_length=2, max_length=24)
    statement: str = Field(min_length=10, max_length=1000)


class CurriculumUnit(StructuredSchema):
    unit_number: int = Field(ge=1, le=20)
    title: str = Field(min_length=2, max_length=200)
    topics: list[str] = Field(min_length=1, max_length=20)


class CurriculumCourseOutcome(StructuredSchema):
    code: str = Field(min_length=2, max_length=24)
    statement: str = Field(min_length=10, max_length=1000)


class CurriculumCourse(StructuredSchema):
    course_code: str = Field(min_length=2, max_length=32)
    title: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=2, max_length=100)
    credits: Decimal = Field(gt=0, le=Decimal("1000"), max_digits=8, decimal_places=2)
    description: str = Field(min_length=10, max_length=2000)
    learning_objectives: list[str] = Field(min_length=1, max_length=20)
    course_outcomes: list[CurriculumCourseOutcome] = Field(min_length=1, max_length=20)
    units: list[CurriculumUnit] = Field(min_length=1, max_length=20)
    teaching_methods: list[str] = Field(min_length=1, max_length=20)
    assessment_methods: list[str] = Field(min_length=1, max_length=20)
    learning_resources: list[str] = Field(min_length=1, max_length=30)


class CurriculumSemester(StructuredSchema):
    semester_number: int = Field(ge=1, le=24)
    title: str = Field(min_length=2, max_length=120)
    courses: list[CurriculumCourse] = Field(min_length=1, max_length=30)


class CurriculumOutcomeMapping(StructuredSchema):
    course_code: str = Field(min_length=2, max_length=32)
    course_outcome_code: str = Field(min_length=2, max_length=24)
    programme_outcome_codes: list[str] = Field(min_length=1, max_length=24)


class GeneratedRegulatoryReference(StructuredSchema):
    rule_id: str = Field(min_length=36, max_length=36)
    application: str = Field(min_length=10, max_length=1000)


class GeneratedCurriculumContent(StructuredSchema):
    programme_overview: str = Field(min_length=20, max_length=4000)
    programme_educational_objectives: list[str] = Field(min_length=1, max_length=20)
    programme_outcomes: list[CurriculumOutcome] = Field(min_length=1, max_length=24)
    programme_specific_outcomes: list[CurriculumOutcome] = Field(min_length=1, max_length=24)
    semesters: list[CurriculumSemester] = Field(min_length=1, max_length=24)
    co_po_mapping: list[CurriculumOutcomeMapping] = Field(min_length=1, max_length=500)
    co_pso_mapping: list[CurriculumOutcomeMapping] = Field(min_length=1, max_length=500)
    regulatory_references: list[GeneratedRegulatoryReference] = Field(min_length=1, max_length=25)


class SemesterCreditDistribution(StructuredSchema):
    semester_number: int = Field(ge=1, le=24)
    credits: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class CurriculumDraftContent(GeneratedCurriculumContent):
    credit_distribution: list[SemesterCreditDistribution] = Field(min_length=1, max_length=24)


class CurriculumRegulatoryEvidence(StructuredSchema):
    rule_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    category: RegulatoryCategoryValue
    issuing_authority: str
    version: str
    effective_date: date | None
    applicability: str
    clause: str | None
    page_number: int | None
    text: str
    application: str


class CurriculumGenerationResponse(BaseModel):
    id: uuid.UUID
    programme_id: uuid.UUID
    status: str
    model: str
    curriculum: CurriculumDraftContent | None
    regulatory_references: list[CurriculumRegulatoryEvidence]
    validation_status: str | None
    validation_checks: list[CreditCheckResult]
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class CurriculumLibraryCreate(BaseModel):
    generation_job_id: uuid.UUID
    title: str | None = Field(default=None, min_length=2, max_length=240)


class CurriculumLibraryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    content: CurriculumDraftContent | None = None


class CurriculumPublishRequest(BaseModel):
    reviewer_id: uuid.UUID
    college_id: uuid.UUID | None = None
    deadline: date | None = None


class CurriculumVersionResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    content: CurriculumDraftContent
    regulatory_references: list[CurriculumRegulatoryEvidence]
    validation_status: str
    validation_checks: list[CreditCheckResult]
    created_at: datetime


class CurriculumLibraryResponse(BaseModel):
    id: uuid.UUID
    generation_job_id: uuid.UUID
    programme_id: uuid.UUID
    programme_name: str
    university_id: uuid.UUID
    university_name: str
    college_id: uuid.UUID | None
    college_name: str | None
    title: str
    academic_year: str
    status: str
    current_version_number: int
    current_version: CurriculumVersionResponse
    created_at: datetime
    updated_at: datetime


class CurriculumAssignmentResponse(BaseModel):
    id: uuid.UUID
    curriculum_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    curriculum_title: str
    programme_name: str
    university_name: str
    college_id: uuid.UUID | None = None
    college_name: str | None = None
    status: str
    deadline: date | None
    published_at: datetime
    validation_status: str


class PublishResult(BaseModel):
    assignment: CurriculumAssignmentResponse
    warning: str | None = None


class NotificationResponse(BaseModel):
    id: uuid.UUID
    title: str
    message: str
    assignment_id: uuid.UUID | None
    created_at: datetime
    read_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class NotificationReadResponse(BaseModel):
    id: uuid.UUID
    read_at: datetime


class ReviewCommentCreate(BaseModel):
    body: str = Field(min_length=2, max_length=8000)
    section_path: str | None = Field(default=None, max_length=500)
    priority: Literal["low", "normal", "high"] = "normal"
    is_submitted: bool = False

    @field_validator("body", "section_path", mode="before")
    @classmethod
    def strip_review_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class ReviewCommentUpdate(BaseModel):
    body: str | None = Field(default=None, min_length=2, max_length=8000)
    section_path: str | None = Field(default=None, max_length=500)
    priority: Literal["low", "normal", "high"] | None = None
    is_submitted: bool | None = None

    @field_validator("body", "section_path", mode="before")
    @classmethod
    def strip_review_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class ReviewCommentReplyCreate(BaseModel):
    body: str = Field(min_length=2, max_length=8000)

    @field_validator("body")
    @classmethod
    def strip_reply_text(cls, value: str) -> str:
        return value.strip()


class ReviewCommentStatusUpdate(BaseModel):
    status: Literal["resolved", "reopened"]


class ReviewDecisionRequest(BaseModel):
    decision: Literal["revision_requested", "reviewer_recommended", "reviewer_rejected"]
    message: str | None = Field(default=None, max_length=2000)

    @field_validator("message")
    @classmethod
    def strip_decision_message(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.decision == "reviewer_rejected" and not self.message:
            raise ValueError("Provide a reason when rejecting a curriculum.")
        return self


class FinalApprovalRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("reason")
    @classmethod
    def strip_final_reason(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.decision == "rejected" and not self.reason:
            raise ValueError("Provide a reason when rejecting a curriculum.")
        return self


class CommentReplyResponse(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    author_role: Role
    body: str
    created_at: datetime


class ReviewCommentResponse(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    section_path: str | None
    priority: str
    body: str
    status: str
    is_submitted: bool
    author_id: uuid.UUID
    author_name: str
    created_at: datetime
    submitted_at: datetime | None
    replies: list[CommentReplyResponse]


class ReviewDocumentResponse(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    version_id: uuid.UUID
    related_comment_id: uuid.UUID | None
    uploaded_by: uuid.UUID
    uploader_name: str
    original_filename: str
    mime_type: str
    file_size: int
    created_at: datetime


class ReviewHistoryResponse(BaseModel):
    id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    actor_id: uuid.UUID
    actor_name: str
    action: str
    details: dict
    created_at: datetime


class ReviewerReviewResponse(BaseModel):
    assignment: CurriculumAssignmentResponse
    curriculum_content: dict
    regulatory_references: list[CurriculumRegulatoryEvidence]
    validation_checks: list[CreditCheckResult]
    comments: list[ReviewCommentResponse]
    documents: list[ReviewDocumentResponse]
    history: list[ReviewHistoryResponse]


class ReviewDecisionResponse(BaseModel):
    assignment: CurriculumAssignmentResponse
    decision: str
    message: str | None


class FinalApprovalResponse(BaseModel):
    assignment: CurriculumAssignmentResponse
    decision: str
    reason: str | None


class CurriculumVersionComparisonResponse(BaseModel):
    curriculum_id: uuid.UUID
    from_version: int
    to_version: int
    changes: list[dict[str, str]]
