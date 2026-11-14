import re
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


class CurriculumStructureCourse(BaseModel):
    course_id: uuid.UUID | None = None
    course_code: str | None = Field(default=None, min_length=2, max_length=32)
    name: str | None = Field(default=None, min_length=2, max_length=200)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    course_type: str | None = Field(default=None, min_length=2, max_length=80)
    credits: Decimal = Field(gt=0, le=Decimal("1000"), max_digits=8, decimal_places=2)

    @model_validator(mode="after")
    def require_manual_course_details(self):
        if self.course_id is None and not all((self.course_code, self.name, self.category, self.course_type)):
            raise ValueError("Provide course details when no legacy course reference is available.")
        return self


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
    password: str = Field(min_length=12, max_length=128)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> EmailStr:
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("Password cannot start or end with whitespace")
        return value


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


class ReviewerPasswordReset(BaseModel):
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("Password cannot start or end with whitespace")
        return value


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

    @field_validator("academic_year", mode="before")
    @classmethod
    def normalize_academic_year(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            match = re.match(r"^(20\d{2})-(\d{2})$", value)
            if match:
                prefix = match.group(1)[:2]
                return f"{match.group(1)}-{prefix}{match.group(2)}"
        return value

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


class RegulatoryDocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    issuing_authority: str
    year: int | None
    version: str
    programme_level: str | None
    applies_to_all_levels: bool = False
    original_filename: str
    page_count: int
    status: str
    created_at: datetime
    rule_count: int
    courses_imported: int = 0


class RegulatoryRuleResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    issuing_authority: str
    year: int | None
    version: str
    programme_level: str | None
    clause: str | None
    page_number: int | None
    text: str
    rule_type: str | None
    category: str | None
    semester: int | None
    value: Decimal | None
    status: str
    verified_at: datetime | None


class RegulatoryRuleUpdate(BaseModel):
    text: str = Field(min_length=4, max_length=4000)
    rule_type: str = Field(pattern=r"^(category_min|category_max|category_total|semester_min|semester_max|semester_total|total_min|total_max|other)$")
    category: str | None = Field(default=None, min_length=2, max_length=100)
    semester: int | None = Field(default=None, ge=1, le=24)
    value: Decimal | None = Field(default=None, ge=0, le=100000, max_digits=10, decimal_places=2)

    @model_validator(mode="after")
    def validate_rule_scope(self):
        if self.rule_type.startswith("category_") and not self.category:
            raise ValueError("Category limits require a category.")
        if self.rule_type.startswith("semester_") and self.semester is None:
            raise ValueError("Semester limits require a semester number.")
        if self.rule_type != "other" and self.value is None:
            raise ValueError("Credit rules require a numeric value.")
        return self


class RegulatoryRuleDecision(BaseModel):
    status: str = Field(pattern=r"^(approved|rejected)$")


class CreditTableSource(BaseModel):
    rule_id: uuid.UUID | None
    document_id: uuid.UUID | None
    rule_text: str | None
    page_number: int | None
    manual: bool
    override_id: uuid.UUID | None = None


class CreditTableRow(BaseModel):
    scope_type: str
    category: str | None
    semester: int | None
    programme_level: str
    programme_duration_years: int | None = None
    credit_value: str | None = None
    minimum: Decimal | None
    maximum: Decimal | None
    total: Decimal | None
    minimum_source: CreditTableSource | None
    maximum_source: CreditTableSource | None
    total_source: CreditTableSource | None


class CreditTableResponse(BaseModel):
    programme_level: str
    rows: list[CreditTableRow]


class CreditTableOverrideCreate(BaseModel):
    programme_level: str = Field(pattern=r"^(ug|pg)$")
    scope_type: str = Field(pattern=r"^(category|semester|total)$")
    category: str | None = Field(default=None, min_length=2, max_length=100)
    semester: int | None = Field(default=None, ge=1, le=24)
    limit_type: str = Field(pattern=r"^(minimum|maximum|total)$")
    value: Decimal = Field(ge=0, le=100000, max_digits=10, decimal_places=2)

    @model_validator(mode="after")
    def validate_override_scope(self):
        if self.scope_type == "category" and not self.category:
            raise ValueError("Category limits require a category.")
        if self.scope_type == "semester" and self.semester is None:
            raise ValueError("Semester limits require a semester.")
        if self.scope_type == "total" and self.limit_type not in {"minimum", "maximum"}:
            raise ValueError("Programme total limits must be minimum or maximum.")
        if self.scope_type == "category" and self.limit_type == "total":
            raise ValueError("Category limits must be minimum or maximum.")
        return self


class CourseCreate(BaseModel):
    course_code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=2, max_length=100)
    semester: int = Field(ge=1, le=24)
    lecture_hours: Decimal = Field(default=Decimal("0"), ge=0, le=1000, max_digits=6, decimal_places=2)
    tutorial_hours: Decimal = Field(default=Decimal("0"), ge=0, le=1000, max_digits=6, decimal_places=2)
    practical_hours: Decimal = Field(default=Decimal("0"), ge=0, le=1000, max_digits=6, decimal_places=2)
    credits: Decimal = Field(gt=0, le=1000, max_digits=8, decimal_places=2)

    @field_validator("course_code")
    @classmethod
    def normalize_course_code(cls, value: str) -> str:
        return value.upper()


class CourseUpdate(BaseModel):
    course_code: str | None = Field(default=None, min_length=2, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    name: str | None = Field(default=None, min_length=2, max_length=200)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    semester: int | None = Field(default=None, ge=1, le=24)
    lecture_hours: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=6, decimal_places=2)
    tutorial_hours: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=6, decimal_places=2)
    practical_hours: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=6, decimal_places=2)
    credits: Decimal | None = Field(default=None, gt=0, le=1000, max_digits=8, decimal_places=2)


class CourseResponse(BaseModel):
    id: uuid.UUID
    course_code: str
    name: str
    category: str
    semester: int
    course_type: str = "theory"
    lecture_hours: Decimal
    tutorial_hours: Decimal
    practical_hours: Decimal
    internal_marks: Decimal = Decimal("0")
    external_marks: Decimal = Decimal("0")
    total_marks: Decimal = Decimal("0")
    credits: Decimal
    status: str
    programme_id: uuid.UUID | None = None


class CourseCategorySummary(BaseModel):
    category: str
    used_credits: Decimal
    minimum: Decimal | None
    maximum: Decimal | None
    status: str


class CourseCreditSummary(BaseModel):
    programme_level: str
    categories: list[CourseCategorySummary]
    total_credits: Decimal


class CourseImportResponse(BaseModel):
    imported: int
    errors: list[str]


class CourseLibraryPaper(BaseModel):
    id: uuid.UUID | None = None
    semester: int = Field(ge=1, le=24)
    paper_code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    paper_title: str = Field(min_length=2, max_length=200)
    paper_type: str = Field(min_length=2, max_length=80)
    category: str = Field(min_length=2, max_length=100)
    lecture_hours: Decimal = Field(ge=0, le=1000, max_digits=6, decimal_places=2)
    tutorial_hours: Decimal = Field(ge=0, le=1000, max_digits=6, decimal_places=2)
    practical_hours: Decimal = Field(ge=0, le=1000, max_digits=6, decimal_places=2)
    internal_marks: Decimal = Field(ge=0, le=10000, max_digits=8, decimal_places=2)
    external_marks: Decimal = Field(ge=0, le=10000, max_digits=8, decimal_places=2)
    credits: Decimal = Field(ge=0, le=1000, max_digits=8, decimal_places=2)

    @field_validator("paper_code")
    @classmethod
    def normalize_library_paper_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("paper_title", "paper_type", "category", mode="before")
    @classmethod
    def strip_library_paper_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class CourseLibrarySave(BaseModel):
    course_name: str = Field(min_length=2, max_length=240)
    course_code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    faculty_school: str = Field(min_length=2, max_length=200)
    department: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=2, max_length=10000)
    regulation_year: str = Field(min_length=2, max_length=20)
    academic_year: str = Field(pattern=r"^20\d{2}-20\d{2}$", min_length=9, max_length=9)
    effective_from: date | None = None
    effective_until: date | None = None
    status: Literal["draft", "active"]
    papers: list[CourseLibraryPaper] = Field(max_length=500)

    @field_validator("academic_year", mode="before")
    @classmethod
    def normalize_academic_year(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            match = re.match(r"^(20\d{2})-(\d{2})$", value)
            if match:
                prefix = match.group(1)[:2]
                return f"{match.group(1)}-{prefix}{match.group(2)}"
        return value

    @field_validator("course_code")
    @classmethod
    def normalize_library_course_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("course_name", "faculty_school", "department", "description", "regulation_year", mode="before")
    @classmethod
    def strip_library_course_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_effective_dates(self):
        if self.effective_from and self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("Effective Until cannot be earlier than Effective From.")
        return self


class CourseLibraryPaperResponse(BaseModel):
    id: uuid.UUID
    semester: int
    paper_code: str
    paper_title: str
    paper_type: str
    category: str
    lecture_hours: Decimal
    tutorial_hours: Decimal
    practical_hours: Decimal
    internal_marks: Decimal
    external_marks: Decimal
    total_marks: Decimal
    credits: Decimal


class CourseLibrarySemesterSummary(BaseModel):
    semester: int
    total_papers: int
    total_credits: Decimal


class CourseCatalogueRow(BaseModel):
    programme_id: uuid.UUID
    course_name: str
    course_code: str
    university_id: uuid.UUID
    university: str
    programme: str
    course_level: str
    duration_years: Decimal
    total_semesters: int
    total_papers: int
    total_credits: Decimal
    status: str


class CourseLibraryDetail(CourseCatalogueRow):
    configured: bool
    faculty_school: str
    department: str
    description: str
    regulation_year: str
    academic_year: str
    effective_from: date | None
    effective_until: date | None
    semesters: list[CourseLibrarySemesterSummary]
    papers: list[CourseLibraryPaperResponse]


class CourseCreditDefaultResponse(BaseModel):
    category: str
    default_credits: Decimal | None
    lecture_hours: Decimal | None
    tutorial_hours: Decimal | None
    practical_hours: Decimal | None
    minimum: Decimal | None
    maximum: Decimal | None
    source: str


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


class GeneratedCurriculumContent(StructuredSchema):
    programme_overview: str = Field(min_length=20, max_length=4000)
    programme_educational_objectives: list[str] = Field(min_length=1, max_length=20)
    programme_outcomes: list[CurriculumOutcome] = Field(min_length=1, max_length=24)
    programme_specific_outcomes: list[CurriculumOutcome] = Field(min_length=1, max_length=24)
    semesters: list[CurriculumSemester] = Field(min_length=1, max_length=24)
    co_po_mapping: list[CurriculumOutcomeMapping] = Field(min_length=1, max_length=500)
    co_pso_mapping: list[CurriculumOutcomeMapping] = Field(min_length=1, max_length=500)

class SemesterCreditDistribution(StructuredSchema):
    semester_number: int = Field(ge=1, le=24)
    credits: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class CurriculumDraftContent(GeneratedCurriculumContent):
    model_config = ConfigDict(extra="ignore")

    credit_distribution: list[SemesterCreditDistribution] = Field(min_length=1, max_length=24)


class CurriculumGenerationResponse(BaseModel):
    id: uuid.UUID
    programme_id: uuid.UUID
    status: str
    model: str
    curriculum: CurriculumDraftContent | None
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
