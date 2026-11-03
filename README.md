# Curriculum Hub

Phase 1–8 implementation of the AI-Powered Curriculum Design & University Review Management System. The repository is split into `frontend/` (React, Vite, TypeScript, Tailwind) and `backend/` (FastAPI, SQLAlchemy, Alembic).

## Implemented scope

- Two account roles: centralized administrator and university reviewer.
- Argon2 password hashing, short-lived JWT access tokens, rotating opaque refresh sessions stored hashed in the database, and sign-out revocation.
- Protected frontend routes and server-enforced role authorization.
- Separate admin and reviewer dashboards backed by database APIs.
- University identity association for reviewer accounts and an initial database migration.
- Bootstrap accounts are optional environment settings. Admins and reviewers use separate sign-in pages at `/login/admin` and `/login/reviewer`; reviewers can register against an existing university/college or request a new university account.
- Admin university management with search, pagination, profile editing, status changes, and reviewer assignment visibility.
- Admin reviewer management with one reviewer per university, university-code login usernames, generated one-time passwords, forced password changes, password reset, and account activation controls. Public reviewer signups remain inactive until an administrator activates them; new university signups require activating both the university and reviewer.
- Admin programme management is university-scoped and includes duration, semester count, level, qualification label, and academic year.
- The Regulatory Knowledge Base accepts regulation PDFs, immediately applies detected complete credit rules, extracts duration-specific undergraduate category values from supported minimum-credit tables, and uses the newest uploaded document with a recognized table for the selected degree duration. It also imports complete course rows from tables when title, category, semester, L–T–P, and credits are present. Existing course codes are preserved; stable codes are generated when omitted. Incomplete course details are not invented.
- The Credit Table switches between 3-year and 4-year degree values. Maximum credits are entered manually for each broad course category.
- The Course Library supports course CRUD, CSV import, and automatically imported courses from supported regulatory PDF tables. Removing a source regulation also removes courses imported from it.
- Curriculum structures support manually entered course descriptions and credit values; they remain separate from regulatory credit-limit extraction.
- Admins can generate and edit structured curriculum drafts using the OpenAI API. Draft generation does not approve or publish a curriculum.
- Curriculum generation sends programme details to OpenAI. Configure `OPENAI_API_KEY` on the backend; `OPENAI_MODEL` defaults to `gpt-4o-mini`. The API key must never be placed in frontend configuration.
- Completed generated drafts can be saved into a searchable curriculum library. Edits create immutable version snapshots and can be exported to DOCX or PDF.
- Admins can publish a selected version to the active reviewer assigned to that programme's university, optionally with a deadline. Reviewer assignment listing and document downloads are scoped to the authenticated reviewer and university.
- Reviewers can open their assigned version, save/submit section-level comments with priorities, upload validated PDF/DOCX corrections, request revisions, recommend approval, or reject with a reason. Decisions and review actions are recorded against the immutable assigned version.
- Administrators can view reviewer assignments and submitted comments, reply, resolve or reopen individual comments, upload revised PDF/DOCX attachments to the current published version, download review attachments, and follow notifications. The feedback screen refreshes from the API every 15 seconds.
- Curriculum content edits create new immutable versions. Administrators can compare version content field-by-field and publish a revised version as a new reviewer assignment; prior assignments, documents, comments, and history remain linked to the earlier version.
- A reviewer can recommend approval or reject with a reason, but cannot grant final approval. Only an authenticated administrator can record the final approval/rejection; final approval is blocked while submitted reviewer comments remain unresolved.
- Review attachments are stored privately outside frontend assets, have randomized storage keys and SHA-256 digests, are validated as readable PDF or DOCX files, and are downloadable only by an administrator or the assigned reviewer.

Historical database tables, Alembic migrations, and stored data are retained. The rebuilt regulatory, credit-table, and course catalogue workflows use the existing records where applicable and add new schema through migration `0020_regulatory_credit_duration`.

## Local development

Requirements: Python 3.12+, Node.js 20+, and npm. SQLite is the local zero-setup database. For PostgreSQL, set `DATABASE_URL` to a SQLAlchemy URL such as `postgresql+psycopg://user:password@localhost:5432/curriculum`.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `backend/.env` to seed the first administrator on startup. To create a local reviewer for dashboard development, also set `REVIEWER_EMAIL`, `REVIEWER_PASSWORD`, `REVIEWER_NAME`, `REVIEWER_UNIVERSITY_NAME`, and `REVIEWER_UNIVERSITY_CODE`. The seeded reviewer is required to change their password at first sign-in. Use unique, strong passwords and a generated `SECRET_KEY`; the example values are for local development only.

Set `OPENAI_API_KEY` in `backend/.env` to enable AI curriculum generation. Programme details are sent to the configured OpenAI model for generation.

Run the backend authentication and role-isolation checks with `python -m pip install -r requirements-dev.txt` followed by `python -m pytest`.

The API is available at `http://localhost:8000`; OpenAPI documentation is at `/docs`. `GET /api/health` checks the database connection.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to the local FastAPI server. The refresh credential is an HttpOnly, SameSite=Lax cookie; the access token stays in memory. Set `COOKIE_SECURE=true` when serving over HTTPS.

## Implemented APIs

- `POST /api/auth/login` — authenticate and issue access/refresh credentials.
- `GET /api/auth/signup-options` and `POST /api/auth/signup` — list available reviewer scopes and submit an inactive reviewer signup.
- `POST /api/auth/refresh` — rotate the refresh session and issue a new access token.
- `POST /api/auth/logout` — revoke the refresh session.
- `GET /api/auth/me` — get the authenticated account.
- `POST /api/auth/change-password` — change a password; minimum 12 characters.
- `GET /api/admin/dashboard` — administrator-only university, reviewer, and programme counts.
- `GET /api/reviewer/dashboard` — reviewer-only overview scoped to the authenticated reviewer.
- `GET /api/universities` — administrator-only searchable university list (`offset`, `limit`, `search`).
- `POST /api/universities` — create a university.
- `PATCH /api/universities/{id}` — update profile details.
- `PATCH /api/universities/{id}/status` — activate or deactivate a university; deactivation also deactivates its reviewer and revokes refresh sessions.
- `GET /api/reviewers` — administrator-only searchable reviewer list.
- `POST /api/reviewers` — create and assign a reviewer; returns a one-time generated temporary password.
- Reviewers can sign in using their email address or their assigned university code as username.
- `PATCH /api/reviewers/{id}` — update reviewer name/email or activation.
- `POST /api/reviewers/{id}/reset-password` — generate a new one-time password, force a password change, and revoke prior refresh sessions.
- `GET /api/programmes` — list programmes with search, university filter, pagination, and status.
- `POST /api/programmes` — create a programme.
- `PATCH /api/programmes/{id}` — edit programme structure or status.
- `POST /api/regulations` and `GET /api/regulations` — upload a regulation PDF with metadata and search/list stored regulations.
- `GET /api/regulations/{id}/download` — download an uploaded regulation PDF.
- `GET /api/regulatory-rules` and `PATCH /api/regulatory-rules/{id}` — search, list, and edit extracted credit-rule drafts.
- `GET /api/credit-table?programme_level=ug|pg` — derive effective limits from extracted credit rules and their rule or manual-override source.
- `PUT /api/credit-table/overrides` and `DELETE /api/credit-table/overrides/{id}` — set or remove a manual credit-limit override.
- `GET /api/courses` and `POST /api/courses` — search and create catalogue courses.
- `PATCH /api/courses/{id}` and `DELETE /api/courses/{id}` — update or delete a course.
- `POST /api/courses/import` — validate and import a CSV course catalogue.
- `GET /api/courses/summary?programme_level=ug|pg` — compare used category credits with effective limits.
- `POST /api/ai-generation/programmes/{id}` — generate a structured curriculum draft with OpenAI.
- `GET /api/ai-generation/programmes/{id}` — list generation history for a programme.
- `GET /api/ai-generation/{job_id}` — retrieve a generation job and its draft.
- `PATCH /api/ai-generation/{job_id}` — edit and save a generated draft.
- `POST /api/curricula` — add a completed generation draft to the central library.
- `GET /api/curricula` — search/filter and sort library entries by programme, university, status, or title.
- `GET /api/curricula/{id}` and `GET /api/curricula/{id}/versions` — retrieve the library item and immutable version history.
- `PATCH /api/curricula/{id}` — update its title or save edited curriculum content as a new version.
- `POST /api/curricula/{id}/archive` — archive a library item; existing reviewer assignments stay linked to their published version.
- `GET /api/curricula/{id}/versions/{version}/export?format=docx|pdf` — download an authenticated Word or PDF export for a selected version.
- `POST /api/curricula/{id}/publish` — publish a version to an active assigned university reviewer with an optional deadline.
- `GET /api/curricula/reviewer/assignments` — list only curricula assigned to the authenticated reviewer.
- `GET /api/curricula/reviewer/assignments/{id}/download?format=docx|pdf` — download only the version assigned to that reviewer.
- `GET /api/curricula/reviewer/notifications` — retrieve publication notifications for the signed-in reviewer.
- `POST /api/curricula/reviewer/notifications/{id}/read` — mark an owned notification as read.
- `GET /api/reviews/assignments/{id}` — retrieve an assigned version and its review data for the assigned reviewer.
- `POST /api/reviews/assignments/{id}/comments` — create a reviewer comment or save it as a draft.
- `PATCH /api/reviews/comments/{id}` — edit and submit an owned reviewer comment draft.
- `POST /api/reviews/assignments/{id}/documents` — upload a private PDF/DOCX correction or annotation.
- `POST /api/reviews/admin/assignments/{id}/documents` — attach an administrator's revised PDF/DOCX to the active current-version assignment.
- `GET /api/reviews/documents/{id}/download` — download a review attachment after administrator/reviewer authorization.
- `POST /api/reviews/assignments/{id}/submit` — request revisions or approve an assignment, subject to comment-state checks.
- `POST /api/reviews/admin/assignments/{id}/final-decision` — administrator-only final approval or reasoned rejection after a reviewer recommendation/rejection or revision request.
- `GET /api/reviews/assignments` — administrator list of review assignments and submitted feedback.
- `POST /api/reviews/comments/{id}/replies` and `PATCH /api/reviews/comments/{id}/status` — administrator reply, resolve, or reopen a submitted comment.
- `GET /api/reviews/curricula/{id}/compare?from_version={n}&to_version={n}` — compare saved curriculum versions.

Review workflow tables (`review_comments`, `comment_replies`, `review_documents`, and `review_history`) are created by Alembic migration `0009_review_workflow`. Configure `REVIEW_STORAGE_DIR` and `REVIEW_MAX_UPLOAD_BYTES` to control private review attachment storage and limits. Configure `REGULATORY_STORAGE_DIR` and `REGULATORY_MAX_UPLOAD_BYTES` for uploaded regulation PDFs.

## Database tables

Runtime tables include `users`, `universities`, `refresh_sessions`, `programmes`, `generation_jobs`, `curricula`, `curriculum_versions`, `curriculum_assignments`, `notifications`, regulatory documents and rules, courses, and credit-table overrides. Alembic migrations are in `backend/migrations/`.

## Planned remaining phases

7. Reviewer document review, comments, and uploads.
8. Feedback, revisions, versioning, notifications, and approvals.
9. End-to-end testing, security hardening, and deployment.
