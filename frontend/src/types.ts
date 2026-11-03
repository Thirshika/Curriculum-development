export type UserRole = "admin" | "reviewer";

export interface User {
  id: string;
  email: string;
  username: string | null;
  full_name: string;
  role: UserRole;
  university_id: string | null;
  university_name: string | null;
  college_id: string | null;
  college_name: string | null;
  must_change_password: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AdminDashboardData {
  total_universities: number;
  reviewer_accounts: number;
  total_programmes: number;
  total_curricula: number;
}

export interface University {
  id: string;
  name: string;
  code: string;
  address: string | null;
  contact_person: string | null;
  contact_email: string | null;
  phone_number: string | null;
  logo_url: string | null;
  status: "active" | "inactive";
  created_at: string;
  reviewer_id: string | null;
  reviewer_name: string | null;
  reviewer_email: string | null;
}

export interface UniversityFormData {
  name: string;
  code: string;
  address: string;
  contact_person: string;
  contact_email: string;
  phone_number: string;
  logo_url: string;
}

export interface Reviewer {
  id: string;
  email: string;
  username: string;
  full_name: string;
  university_id: string;
  university_name: string;
  university_code: string;
  college_id: string | null;
  college_name: string | null;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
}

export interface College {
  id: string;
  university_id: string;
  university_name: string;
  name: string;
  code: string;
  address: string | null;
  state: string | null;
  district: string | null;
  contact_person: string | null;
  contact_email: string | null;
  phone_number: string | null;
  website: string | null;
  status: "active" | "inactive";
  reviewer_id: string | null;
  reviewer_name: string | null;
  reviewer_email: string | null;
  programme_count: number;
  assignment_count: number;
  created_at: string;
}

export interface CurriculumStructure {
  id: string;
  programme_id: string;
  programme_name: string;
  university_name: string;
  college_id: string | null;
  college_name: string | null;
  title: string;
  current_version: number;
  version: {
    id: string;
    version_number: number;
    content: { semesters: { semester_number: number; courses: { course_id?: string; course_code: string; name: string; category: string; course_type: string; credits: string }[] }[] };
    created_at: string;
  };
  created_at: string;
  updated_at: string;
}

export interface ProvisionedReviewer {
  reviewer: Reviewer;
  temporary_password: string;
}

export interface Programme {
  id: string;
  university_id: string;
  college_id: string | null;
  college_name: string | null;
  university_name: string;
  university_code: string;
  name: string;
  degree_type: string;
  specialization: string | null;
  level: "ug" | "pg" | "doctoral" | "certificate" | "diploma" | "other";
  duration_years: string;
  semester_count: number;
  academic_year: string;
  qualification_level: string | null;
  status: "active" | "inactive";
  created_at: string;
  updated_at: string;
}

export interface RegulatoryDocument {
  id: string;
  title: string;
  issuing_authority: string;
  year: number | null;
  version: string;
  programme_level: "ug" | "pg" | null;
  applies_to_all_levels: boolean;
  original_filename: string;
  page_count: number;
  status: string;
  created_at: string;
  rule_count: number;
  courses_imported: number;
}

export interface RegulatoryRule {
  id: string;
  document_id: string;
  document_title: string;
  issuing_authority: string;
  year: number | null;
  version: string;
  programme_level: "ug" | "pg" | null;
  clause: string | null;
  page_number: number | null;
  text: string;
  rule_type: "category_min" | "category_max" | "category_total" | "semester_min" | "semester_max" | "semester_total" | "total_min" | "total_max" | "other" | null;
  category: string | null;
  semester: number | null;
  value: string | null;
  status: "applied" | "informational" | "ignored";
  verified_at: string | null;
}

export interface CreditTableSource {
  rule_id: string | null;
  document_id: string | null;
  rule_text: string | null;
  page_number: number | null;
  manual: boolean;
  override_id?: string | null;
}

export interface CreditTableRow {
  scope_type: "category" | "semester" | "total";
  category: string | null;
  semester: number | null;
  programme_level: "ug" | "pg";
  programme_duration_years?: number | null;
  credit_value?: string | null;
  minimum: string | null;
  maximum: string | null;
  total: string | null;
  minimum_source: CreditTableSource | null;
  maximum_source: CreditTableSource | null;
  total_source: CreditTableSource | null;
}

export interface Course {
  id: string;
  course_code: string;
  name: string;
  category: string;
  semester: number;
  lecture_hours: string;
  tutorial_hours: string;
  practical_hours: string;
  credits: string;
  status: "active" | "archived";
}

export interface CourseCreditCategory {
  category: string;
  used_credits: string;
  minimum: string | null;
  maximum: string | null;
  status: "not_configured" | "within_limit" | "outside_limit";
}

export interface CourseCreditSummary {
  programme_level: "ug" | "pg";
  categories: CourseCreditCategory[];
  total_credits: string;
}

export interface CurriculumOutcome {
  code: string;
  statement: string;
}

export interface CurriculumCourseOutcome {
  code: string;
  statement: string;
}

export interface CurriculumUnit {
  unit_number: number;
  title: string;
  topics: string[];
}

export interface CurriculumCourse {
  course_code: string;
  title: string;
  category: string;
  credits: string;
  description: string;
  learning_objectives: string[];
  course_outcomes: CurriculumCourseOutcome[];
  units: CurriculumUnit[];
  teaching_methods: string[];
  assessment_methods: string[];
  learning_resources: string[];
}

export interface CurriculumSemester {
  semester_number: number;
  title: string;
  courses: CurriculumCourse[];
}

export interface CurriculumOutcomeMapping {
  course_code: string;
  course_outcome_code: string;
  programme_outcome_codes: string[];
}

export interface SemesterCreditDistribution {
  semester_number: number;
  credits: string;
}

export interface CurriculumDraftContent {
  programme_overview: string;
  programme_educational_objectives: string[];
  programme_outcomes: CurriculumOutcome[];
  programme_specific_outcomes: CurriculumOutcome[];
  semesters: CurriculumSemester[];
  co_po_mapping: CurriculumOutcomeMapping[];
  co_pso_mapping: CurriculumOutcomeMapping[];
  credit_distribution: SemesterCreditDistribution[];
}

export interface CurriculumGeneration {
  id: string;
  programme_id: string;
  status: "generating" | "completed" | "failed";
  model: string;
  curriculum: CurriculumDraftContent | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface CurriculumVersion {
  id: string;
  version_number: number;
  content: CurriculumDraftContent;
  created_at: string;
}

export interface CurriculumLibraryItem {
  id: string;
  generation_job_id: string;
  programme_id: string;
  programme_name: string;
  university_id: string;
  university_name: string;
  college_id: string | null;
  college_name: string | null;
  title: string;
  academic_year: string;
  status: "draft" | "published" | "archived";
  current_version_number: number;
  current_version: CurriculumVersion;
  created_at: string;
  updated_at: string;
}

export interface ReviewerAssignment {
  id: string;
  curriculum_id: string;
  version_id: string;
  version_number: number;
  curriculum_title: string;
  programme_name: string;
  university_name: string;
  college_id: string | null;
  college_name: string | null;
  status: string;
  deadline: string | null;
  published_at: string;
}

export interface CurriculumNotification {
  id: string;
  title: string;
  message: string;
  assignment_id: string | null;
  created_at: string;
  read_at: string | null;
}

export interface ReviewCommentReply {
  id: string;
  author_id: string;
  author_name: string;
  author_role: "admin" | "reviewer";
  body: string;
  created_at: string;
}

export interface ReviewComment {
  id: string;
  assignment_id: string;
  version_id: string;
  version_number: number;
  section_path: string | null;
  priority: string;
  body: string;
  status: string;
  is_submitted: boolean;
  author_id: string;
  author_name: string;
  created_at: string;
  submitted_at: string | null;
  replies: ReviewCommentReply[];
}

export interface ReviewDocument {
  id: string;
  assignment_id: string;
  version_id: string;
  related_comment_id: string | null;
  uploaded_by: string;
  uploader_name: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  created_at: string;
}

export interface ReviewHistoryEntry {
  id: string;
  version_id: string;
  version_number: number;
  actor_id: string;
  actor_name: string;
  action: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface ReviewerReviewData {
  assignment: ReviewerAssignment;
  curriculum_content: CurriculumDraftContent;
  comments: ReviewComment[];
  documents: ReviewDocument[];
  history: ReviewHistoryEntry[];
}

export interface ReviewerAccount {
  id: string;
  email: string;
  username: string;
  full_name: string;
  university_id: string;
  university_name: string;
  university_code: string;
  college_id: string | null;
  college_name: string | null;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
}

export interface ReviewerDashboardData {
  university_name: string;
  assigned_curricula: number;
  pending_reviews: number;
  under_review: number;
  revision_requested: number;
  approved_curricula: number;
}
