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
- Regulatory PDF/DOCX intake, text and table extraction, local 384-dimensional feature-hashing embeddings, searchable chunks, candidate-rule extraction, verification, conflict flags, version history, and archival.
- Regulatory retrieval is restricted to verified rules from active documents; regulatory uploads do not train an AI model and are not sent to an external embedding service.
- Feature-hashing retrieval is lexical rather than a semantic language model; extracted rules are heuristic candidates and require an administrator to verify their source and meaning.
- Admin programme management is university-scoped and includes duration, semester count, level, qualification label, academic year, and applicable source documents.
- Deterministic credit validation evaluates only numeric thresholds explicitly configured against verified, unconflicted rules from active source versions, and stores each validation with the relevant regulatory evidence.
- Supported configured checks are minimum/maximum total credits, minimum/maximum credits per semester, minimum/maximum programme duration, and minimum/maximum semester count. If no applicable checks are configured, validation is `incomplete`; a `passed` result means only that the configured checks passed, not that the programme is fully compliant.
- Admins can generate and edit structured curriculum drafts using the OpenAI API and retrieved rules from active, programme-mapped sources that are verified and not conflict-flagged. Generated course-credit distributions are computed and checked by the deterministic engine; citations are validated against the retrieved source rules. Draft generation does not approve or publish a curriculum.
- Curriculum generation sends programme details and retrieved regulatory excerpts to OpenAI. Configure `OPENAI_API_KEY` on the backend; `OPENAI_MODEL` defaults to `gpt-4o-mini`. The API key must never be placed in frontend configuration.
- Completed generated drafts can be saved into a searchable curriculum library. Edits create immutable version snapshots; each version keeps its source citations and deterministic validation result and can be exported to DOCX or PDF.
- Admins can publish a selected version to the active reviewer assigned to that programme's university, optionally with a deadline. Publishing a failed credit-validation version is blocked; an incomplete result is published with an explicit warning. Reviewer assignment listing and document downloads are scoped to the authenticated reviewer and university.
- Reviewers can open their assigned version, save/submit section-level comments with priorities, upload validated PDF/DOCX corrections, request revisions, recommend approval, or reject with a reason. Decisions and review actions are recorded against the immutable assigned version.
- Administrators can view reviewer assignments and submitted comments, reply, resolve or reopen individual comments, upload revised PDF/DOCX attachments to the current published version, download review attachments, and follow notifications. The feedback screen refreshes from the API every 15 seconds.
- Curriculum content edits create new immutable versions. Administrators can compare version content field-by-field and publish a revised version as a new reviewer assignment; prior assignments, documents, comments, and history remain linked to the earlier version.
- A reviewer can recommend approval or reject with a reason, but cannot grant final approval. Only an authenticated administrator can record the final approval/rejection; final approval is blocked while submitted reviewer comments remain unresolved.
- Review attachments are stored privately outside frontend assets, have randomized storage keys and SHA-256 digests, are validated as readable PDF or DOCX files, and are downloadable only by an administrator or the assigned reviewer.

Phase 9 security hardening, deployment configuration, and final end-to-end testing remain.

The supplementary specification introduces additional modules beyond the original nine-phase baseline. These are not yet implemented: college-level organization and reviewer isolation, a reusable course catalogue and manual curriculum designer, the richer category/compliance checklist validators, dedicated role-selection/forgot-password screens, reviewer profile editing, and analytics/report exports. These will be added without replacing the existing university-level workflows; college-level reviewer scoping needs its own additive schema migration and end-to-end isolation tests.

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

Set `OPENAI_API_KEY` in `backend/.env` to enable AI curriculum generation. Programme descriptions and selected verified regulatory excerpts are sent to the configured OpenAI model for generation.

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
- `POST /api/regulations` — privately upload a PDF/DOCX, extract text and tables, create searchable chunks and candidate rules.
- `GET /api/regulations` — search and filter regulatory source versions.
- `GET /api/regulations/{id}/text` and `GET /api/regulations/{id}/download` — admin-protected extracted-text preview and source download.
- `POST /api/regulations/{id}/archive` — archive a source; archived rules are excluded from retrieval.
- `GET /api/regulatory-rules` — filter extracted rules by source, verification status, and conflict state.
- `PATCH /api/regulatory-rules/{id}/verification` — verify or reject an extracted rule with an admin audit identity and timestamp.
- `PATCH /api/regulatory-rules/{id}/conflict` — flag or clear a potential conflict; flagged rules are excluded from retrieval.
- `POST /api/regulatory-rules/retrieve` — retrieve the best-matching, verified, unconflicted rules from active sources.
- `PUT /api/regulatory-rules/{id}/credit-constraint` — configure one supported numeric credit/duration/semester threshold explicitly from a verified, unconflicted rule.
- `GET /api/regulatory-rules/credit-constraints` — list currently applicable configured numeric thresholds.
- `GET /api/programmes` — list programmes with search, university filter, pagination, status, and mapped source metadata.
- `POST /api/programmes` — create a programme and map active, university-applicable regulatory source documents.
- `PATCH /api/programmes/{id}` — edit programme structure, status, or applicable sources.
- `POST /api/programmes/{id}/validate-credits` — calculate the credit total and evaluate applicable configured constraints, persisting an evidence-backed validation run.
- `GET /api/programmes/{id}/validations` — retrieve paginated credit-validation history.
- `POST /api/ai-generation/programmes/{id}` — retrieve applicable verified rules, generate a structured curriculum draft with OpenAI, validate its citations and shape, and deterministically check its semester credit distribution.
- `GET /api/ai-generation/programmes/{id}` — list generation history for a programme.
- `GET /api/ai-generation/{job_id}` — retrieve a generation job and its draft/evidence.
- `PATCH /api/ai-generation/{job_id}` — edit and save a generated draft; recalculates semester credits and configured regulatory checks.
- `POST /api/curricula` — add a completed generation draft to the central library.
- `GET /api/curricula` — search/filter and sort library entries by programme, university, status, or title.
- `GET /api/curricula/{id}` and `GET /api/curricula/{id}/versions` — retrieve the library item and immutable version history.
- `PATCH /api/curricula/{id}` — update its title or save edited curriculum content as a new validated version.
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

Review workflow tables (`review_comments`, `comment_replies`, `review_documents`, and `review_history`) are created by Alembic migration `0009_review_workflow`. Configure `REVIEW_STORAGE_DIR` and `REVIEW_MAX_UPLOAD_BYTES` to control private review attachment storage and limits.

## Database tables

`users`, `universities`, `refresh_sessions` (hashed, revocable refresh credentials), `regulatory_documents`, `regulatory_chunks`, `regulatory_rules`, `credit_constraints`, `programmes`, `programme_regulatory_mappings`, `credit_validation_runs`, `generation_jobs` (structured curriculum drafts), `curricula`, `curriculum_versions` (immutable snapshots with evidence and validation), `curriculum_assignments` (reviewer-scoped publication records), and `notifications` (in-app assignment notices). Alembic migrations are in `backend/migrations/versions/`. PostgreSQL stores 384-dimensional vectors in pgvector; SQLite uses JSON vectors for local development. Uploaded source files live under `REGULATORY_STORAGE_DIR`, outside public frontend assets.

## Planned remaining phases

7. Reviewer document review, comments, and uploads.
8. Feedback, revisions, versioning, notifications, and approvals.
9. End-to-end testing, security hardening, and deployment.
