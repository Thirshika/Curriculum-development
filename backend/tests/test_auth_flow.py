import pytest
import pymupdf
from docx import Document as WordDocument
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.config import settings
from app.main import app
from app.models import University, User, UserRole
from app.security import hash_password


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(settings, "regulatory_storage_dir", tmp_path / "regulations")
    monkeypatch.setattr(settings, "review_storage_dir", tmp_path / "reviews")
    Base.metadata.create_all(bind=test_engine)
    university = University(name="ABC University", code="ABC001")
    admin = User(
        email="admin@example.com",
        full_name="Platform Admin",
        password_hash=hash_password("admin-test-password"),
        role=UserRole.ADMIN,
    )
    reviewer = User(
        email="reviewer@example.com",
        full_name="ABC Reviewer",
        password_hash=hash_password("reviewer-test-password"),
        role=UserRole.REVIEWER,
        university_id=university.id,
        must_change_password=True,
    )
    with TestingSession() as db:
        db.add(university)
        db.flush()
        reviewer.university_id = university.id
        db.add_all([admin, reviewer])
        db.commit()

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def test_admin_login_dashboard_and_role_boundaries(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin-test-password"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "admin"
    assert "curriculum_refresh" in login.cookies

    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    dashboard = client.get("/api/admin/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json() == {
        "total_universities": 1,
        "reviewer_accounts": 1,
        "total_programmes": 0,
        "total_curricula": 0,
    }
    assert client.get("/api/reviewer/dashboard", headers=headers).status_code == 403


def test_reviewer_is_scoped_and_cannot_access_admin_api(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "reviewer@example.com", "password": "reviewer-test-password"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert login.json()["user"]["must_change_password"] is True
    assert client.get("/api/reviewer/dashboard", headers=headers).status_code == 403
    password_change = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={
            "current_password": "reviewer-test-password",
            "new_password": "updated-reviewer-test-password",
        },
    )
    assert password_change.status_code == 200
    dashboard = client.get("/api/reviewer/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["university_name"] == "ABC University"
    assert client.get("/api/admin/dashboard", headers=headers).status_code == 403
    assert client.get("/api/universities", headers=headers).status_code == 403


def test_refresh_rotates_and_logout_revokes_session(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin-test-password"},
    )
    old_refresh = login.cookies["curriculum_refresh"]
    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.cookies["curriculum_refresh"] != old_refresh

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert client.post("/api/auth/refresh").status_code == 401


def test_temporary_password_must_be_changed(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "reviewer@example.com", "password": "reviewer-test-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    rejected = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "reviewer-test-password", "new_password": "short"},
    )
    assert rejected.status_code == 422

    changed = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={
            "current_password": "reviewer-test-password",
            "new_password": "a-stronger-test-password",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
    assert client.post(
        "/api/auth/login",
        json={"email": "reviewer@example.com", "password": "a-stronger-test-password"},
    ).status_code == 200


def test_unauthenticated_routes_are_protected(client):
    assert client.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/reviewer/dashboard").status_code == 401
    assert client.get("/api/universities").status_code == 401
    assert client.get("/api/reviewers").status_code == 401


def admin_headers(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin-test-password"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_reviewer_signup_requires_admin_activation_and_uses_reviewer_login(client):
    headers = admin_headers(client)
    created_university = client.post(
        "/api/universities",
        headers=headers,
        json={"name": "Signup University", "code": "SIGNUP001"},
    )
    assert created_university.status_code == 201
    university_id = created_university.json()["id"]

    signup = client.post(
        "/api/auth/signup",
        json={
            "full_name": "New Reviewer",
            "email": "new-reviewer@example.com",
            "password": "a-strong-signup-password",
            "university_id": university_id,
        },
    )
    assert signup.status_code == 201
    assert "administrator must approve" in signup.json()["message"]
    assert client.post(
        "/api/auth/login",
        json={
            "email": "new-reviewer@example.com",
            "password": "a-strong-signup-password",
            "expected_role": "reviewer",
        },
    ).status_code == 401

    reviewer_list = client.get("/api/reviewers", headers=headers)
    assert reviewer_list.status_code == 200
    reviewer = next(item for item in reviewer_list.json() if item["email"] == "new-reviewer@example.com")
    assert reviewer["is_active"] is False
    assert reviewer["username"] == "SIGNUP001"
    activated = client.patch(
        f"/api/reviewers/{reviewer['id']}",
        headers=headers,
        json={"is_active": True},
    )
    assert activated.status_code == 200

    login = client.post(
        "/api/auth/login",
        json={
            "email": "new-reviewer@example.com",
            "password": "a-strong-signup-password",
            "expected_role": "reviewer",
        },
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "reviewer"
    assert client.post(
        "/api/auth/login",
        json={
            "email": "new-reviewer@example.com",
            "password": "a-strong-signup-password",
            "expected_role": "admin",
        },
    ).status_code == 401


def test_new_university_signup_stays_pending_until_both_records_are_approved(client):
    signup = client.post(
        "/api/auth/signup",
        json={
            "full_name": "New Institution Reviewer",
            "email": "institution-reviewer@example.com",
            "password": "another-strong-signup-password",
            "new_university_name": "New Institution",
            "new_university_code": "newinst001",
        },
    )
    assert signup.status_code == 201

    headers = admin_headers(client)
    universities = client.get(
        "/api/universities",
        headers=headers,
        params={"search": "New Institution"},
    )
    assert universities.status_code == 200
    university = universities.json()[0]
    assert university["code"] == "NEWINST001"
    assert university["status"] == "inactive"

    reviewers = client.get("/api/reviewers", headers=headers)
    reviewer = next(item for item in reviewers.json() if item["email"] == "institution-reviewer@example.com")
    assert reviewer["is_active"] is False

    university_activated = client.patch(
        f"/api/universities/{university['id']}/status",
        headers=headers,
        json={"status": "active"},
    )
    assert university_activated.status_code == 200
    reviewer_activated = client.patch(
        f"/api/reviewers/{reviewer['id']}",
        headers=headers,
        json={"is_active": True},
    )
    assert reviewer_activated.status_code == 200

    login = client.post(
        "/api/auth/login",
        json={
            "email": "institution-reviewer@example.com",
            "password": "another-strong-signup-password",
            "expected_role": "reviewer",
        },
    )
    assert login.status_code == 200


def test_university_management_validates_code_and_deactivates_reviewer(client):
    headers = admin_headers(client)
    created = client.post(
        "/api/universities",
        headers=headers,
        json={
            "name": "  XYZ University  ",
            "code": "xyz001",
            "address": "12 Campus Road",
            "contact_person": "Registrar",
            "contact_email": "registrar@example.com",
            "phone_number": "+1 555 0100",
        },
    )
    assert created.status_code == 201
    university = created.json()
    assert university["code"] == "XYZ001"
    assert university["address"] == "12 Campus Road"

    duplicate = client.post(
        "/api/universities",
        headers=headers,
        json={"name": "Another University", "code": "xyz001"},
    )
    assert duplicate.status_code == 409
    listing = client.get("/api/universities", headers=headers, params={"search": "XYZ"})
    assert [item["id"] for item in listing.json()] == [university["id"]]

    updated = client.patch(
        f"/api/universities/{university['id']}",
        headers=headers,
        json={"contact_person": "New Registrar"},
    )
    assert updated.status_code == 200
    assert updated.json()["contact_person"] == "New Registrar"

    abc = client.get("/api/universities", headers=headers, params={"search": "ABC"}).json()[0]
    deactivated = client.patch(
        f"/api/universities/{abc['id']}/status",
        headers=headers,
        json={"status": "inactive"},
    )
    assert deactivated.status_code == 200
    reviewer_login = client.post(
        "/api/auth/login",
        json={"email": "reviewer@example.com", "password": "reviewer-test-password"},
    )
    assert reviewer_login.status_code == 401

    reactivated = client.patch(
        f"/api/universities/{abc['id']}/status",
        headers=headers,
        json={"status": "active"},
    )
    assert reactivated.status_code == 200
    reviewers = client.get("/api/reviewers", headers=headers).json()
    assert next(item for item in reviewers if item["university_id"] == abc["id"])["is_active"] is False


def test_reviewer_provisioning_one_per_university_and_password_reset(client):
    headers = admin_headers(client)
    university = client.post(
        "/api/universities",
        headers=headers,
        json={"name": "XYZ University", "code": "XYZ001"},
    ).json()
    created = client.post(
        "/api/reviewers",
        headers=headers,
        json={
            "university_id": university["id"],
            "full_name": "XYZ Reviewer",
            "email": "xyz-reviewer@example.com",
        },
    )
    assert created.status_code == 201
    provisioned = created.json()
    assert provisioned["reviewer"]["must_change_password"] is True
    assert provisioned["reviewer"]["username"] == "XYZ001"
    assert len(provisioned["temporary_password"]) >= 16

    duplicate = client.post(
        "/api/reviewers",
        headers=headers,
        json={
            "university_id": university["id"],
            "full_name": "Second Reviewer",
            "email": "second-reviewer@example.com",
        },
    )
    assert duplicate.status_code == 409

    reviewer_id = provisioned["reviewer"]["id"]
    username_login = client.post(
        "/api/auth/login",
        json={"username": "xyz001", "password": provisioned["temporary_password"]},
    )
    assert username_login.status_code == 200
    assert username_login.json()["user"]["username"] == "XYZ001"

    updated = client.patch(
        f"/api/reviewers/{reviewer_id}",
        headers=headers,
        json={"full_name": "Updated XYZ Reviewer"},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Updated XYZ Reviewer"

    reset = client.post(f"/api/reviewers/{reviewer_id}/reset-password", headers=headers)
    assert reset.status_code == 200
    reset_password = reset.json()["temporary_password"]
    assert reset_password != provisioned["temporary_password"]
    old_password_login = client.post(
        "/api/auth/login",
        json={"email": "xyz-reviewer@example.com", "password": provisioned["temporary_password"]},
    )
    assert old_password_login.status_code == 401
    new_password_login = client.post(
        "/api/auth/login",
        json={"email": "xyz-reviewer@example.com", "password": reset_password},
    )
    assert new_password_login.status_code == 200
    assert new_password_login.json()["user"]["must_change_password"] is True


def test_reviewer_cannot_manage_universities_or_reviewer_accounts(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "reviewer@example.com", "password": "reviewer-test-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/universities", headers=headers).status_code == 403
    assert client.get("/api/reviewers", headers=headers).status_code == 403
    assert client.post(
        "/api/universities",
        headers=headers,
        json={"name": "Unauthorized", "code": "NOPE001"},
    ).status_code == 403


def regulatory_admin_headers(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "admin-test-password"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def sample_regulatory_pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50, 60), text)
    content = document.tobytes()
    document.close()
    return content


def upload_regulatory_pdf(client, headers, title="National Credit Framework"):
    return client.post(
        "/api/regulations",
        headers=headers,
        data={
            "category": "ncrf",
            "title": title,
            "issuing_authority": "UGC",
            "version": "2023",
            "effective_date": "2023-06-01",
            "applicability": "Undergraduate programmes",
        },
        files={
            "file": (
                "ncrf.pdf",
                sample_regulatory_pdf(
                    "Section 4.1: All undergraduate programmes must include at least 120 credits. "
                    "Institutions shall maintain the approved programme duration."
                ),
                "application/pdf",
            )
        },
    )


def test_regulatory_upload_extract_chunk_verify_and_retrieve(client):
    headers = regulatory_admin_headers(client)
    uploaded = upload_regulatory_pdf(client, headers)
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["category"] == "ncrf"
    assert document["effective_date"] == "2023-06-01"
    assert document["chunk_count"] >= 1
    assert document["pending_rules"] >= 1

    text_response = client.get(f"/api/regulations/{document['id']}/text", headers=headers)
    assert text_response.status_code == 200
    assert "120 credits" in text_response.json()["extracted_text"]

    rules = client.get(
        "/api/regulatory-rules",
        headers=headers,
        params={"document_id": document["id"], "verification_status": "pending"},
    )
    assert rules.status_code == 200
    assert rules.json()
    rule = next(item for item in rules.json() if "120 credits" in item["text"])
    assert rule["clause"] == "Section 4.1"
    assert rule["page_number"] == 1

    before_verification = client.post(
        "/api/regulatory-rules/retrieve",
        headers=headers,
        json={"query": "minimum credits for undergraduate programmes"},
    )
    assert before_verification.status_code == 200
    assert all(item["document_id"] != document["id"] for item in before_verification.json())

    verified = client.patch(
        f"/api/regulatory-rules/{rule['id']}/verification",
        headers=headers,
        json={"verification_status": "verified"},
    )
    assert verified.status_code == 200
    retrieved = client.post(
        "/api/regulatory-rules/retrieve",
        headers=headers,
        json={"query": "minimum credits for undergraduate programmes", "categories": ["ncrf"]},
    )
    assert retrieved.status_code == 200
    assert retrieved.json()
    assert retrieved.json()[0]["rule_id"] == rule["id"]
    assert retrieved.json()[0]["similarity"] > 0

    download = client.get(f"/api/regulations/{document['id']}/download", headers=headers)
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF-")
    assert client.get(f"/api/regulations/{document['id']}/download").status_code == 401


def test_programme_management_and_deterministic_credit_validation(client):
    headers = regulatory_admin_headers(client)
    source_response = upload_regulatory_pdf(client, headers, "ABC Undergraduate Credit Rule")
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    rules = client.get(
        "/api/regulatory-rules",
        headers=headers,
        params={"document_id": source["id"], "verification_status": "pending"},
    ).json()
    rule = next(item for item in rules if "120 credits" in item["text"])
    assert client.patch(
        f"/api/regulatory-rules/{rule['id']}/verification",
        headers=headers,
        json={"verification_status": "verified"},
    ).status_code == 200
    constraint = client.put(
        f"/api/regulatory-rules/{rule['id']}/credit-constraint",
        headers=headers,
        json={"kind": "min_total_credits", "value": "120"},
    )
    assert constraint.status_code == 200, constraint.text
    assert constraint.json()["document_id"] == source["id"]

    university = client.get("/api/universities", headers=headers, params={"search": "ABC"}).json()[0]
    programme_response = client.post(
        "/api/programmes",
        headers=headers,
        json={
            "university_id": university["id"],
            "name": "B.E. Computer Science",
            "degree_type": "B.E.",
            "specialization": "Computer Science",
            "level": "ug",
            "duration_years": "4",
            "semester_count": 2,
            "academic_year": "2027-2028",
            "qualification_level": "Level 6",
            "regulatory_document_ids": [source["id"]],
        },
    )
    assert programme_response.status_code == 201, programme_response.text
    programme = programme_response.json()
    assert programme["university_code"] == "ABC001"
    assert programme["applicable_regulations"][0]["constraints"][0]["kind"] == "min_total_credits"

    failed = client.post(
        f"/api/programmes/{programme['id']}/validate-credits",
        headers=headers,
        json={"semester_credits": [50, 60]},
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["total_credits"] == "110.00"
    assert failed.json()["status"] == "failed"
    assert failed.json()["checks"][0]["rule_id"] == rule["id"]
    assert failed.json()["checks"][0]["document_title"] == source["title"]

    passed = client.post(
        f"/api/programmes/{programme['id']}/validate-credits",
        headers=headers,
        json={"semester_credits": [60, 60]},
    )
    assert passed.json()["total_credits"] == "120.00"
    assert passed.json()["status"] == "passed"
    assert client.get(
        f"/api/programmes/{programme['id']}/validations",
        headers=headers,
    ).json()[0]["id"] == passed.json()["id"]

    assert client.patch(
        f"/api/regulatory-rules/{rule['id']}/conflict",
        headers=headers,
        json={"has_conflict": True, "conflict_note": "Review a possible superseding rule"},
    ).status_code == 200
    with_conflict = client.post(
        f"/api/programmes/{programme['id']}/validate-credits",
        headers=headers,
        json={"semester_credits": [60, 60]},
    )
    assert with_conflict.json()["status"] == "incomplete"
    assert with_conflict.json()["configured_constraint_count"] == 0
    assert "cannot establish compliance" in with_conflict.json()["checks"][0]["message"]

    archived = client.post(f"/api/regulations/{source['id']}/archive", headers=headers)
    assert archived.status_code == 200
    still_mapped = client.get("/api/programmes", headers=headers, params={"university_id": university["id"]}).json()[0]
    assert still_mapped["applicable_regulations"][0]["status"] == "archived"
    edited = client.patch(
        f"/api/programmes/{programme['id']}",
        headers=headers,
        json={"regulatory_document_ids": [source["id"]]},
    )
    assert edited.status_code == 200, edited.text

    invalid_plan = client.post(
        f"/api/programmes/{programme['id']}/validate-credits",
        headers=headers,
        json={"semester_credits": [100]},
    )
    assert invalid_plan.status_code == 200
    assert invalid_plan.json()["status"] == "failed"
    assert "Expected a credit allocation for 2 semesters" in invalid_plan.json()["checks"][0]["message"]


def test_course_library_and_manual_curriculum_versions(client):
    headers = admin_headers(client)
    university = client.get("/api/universities", headers=headers, params={"search": "ABC"}).json()[0]
    programme_response = client.post(
        "/api/programmes",
        headers=headers,
        json={
            "university_id": university["id"],
            "name": "Manual Design Programme",
            "degree_type": "BSc",
            "level": "ug",
            "duration_years": "1",
            "semester_count": 2,
            "academic_year": "2028-2029",
        },
    )
    assert programme_response.status_code == 201, programme_response.text
    programme = programme_response.json()

    course_ids = []
    for code, name, category in [
        ("MD101", "Design Foundations", "Major"),
        ("MD102", "Applied Design", "Major"),
    ]:
        response = client.post(
            "/api/courses",
            headers=headers,
            json={
                "course_code": code,
                "name": name,
                "category": category,
                "credits": "60",
                "programme_ids": [programme["id"]],
            },
        )
        assert response.status_code == 201, response.text
        course_ids.append(response.json()["id"])

    payload = {
        "programme_id": programme["id"],
        "title": "Manual curriculum",
        "content": {
            "semesters": [
                {"semester_number": 1, "courses": [{"course_id": course_ids[0], "credits": "60"}]},
                {"semester_number": 2, "courses": [{"course_id": course_ids[1], "credits": "60"}]},
            ],
        },
    }
    created = client.post("/api/curriculum-structures", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    structure = created.json()
    assert structure["current_version"] == 1
    assert structure["version"]["content"]["semesters"][0]["courses"][0]["course_id"] == course_ids[0]

    updated = client.patch(
        f"/api/curriculum-structures/{structure['id']}",
        headers=headers,
        json={"content": payload["content"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["current_version"] == 2
    assert updated.json()["version"]["version_number"] == 2

    validated = client.post(f"/api/curriculum-structures/{structure['id']}/validate", headers=headers)
    assert validated.status_code == 200, validated.text
    assert validated.json()["version"]["validation"]["total_credits"] == "120.00"
    assert validated.json()["version"]["validation"]["configured_constraint_count"] == 0

    invalid = client.post(
        "/api/curriculum-structures",
        headers=headers,
        json={**payload, "title": "Incomplete", "content": {"semesters": [
            {"semester_number": 1, "courses": [{"course_id": "00000000-0000-0000-0000-000000000000", "credits": "3"}]},
            {"semester_number": 2, "courses": [{"course_id": course_ids[1], "credits": "3"}]},
        ]}},
    )
    assert invalid.status_code == 422


def test_college_management_scopes_reviewer_accounts(client):
    headers = admin_headers(client)
    university = client.get("/api/universities", headers=headers, params={"search": "ABC"}).json()[0]
    college = client.post(
        "/api/colleges",
        headers=headers,
        json={"university_id": university["id"], "name": "North Campus", "code": "NORTH"},
    )
    assert college.status_code == 201, college.text

    created = client.post(
        "/api/reviewers",
        headers=headers,
        json={
            "university_id": university["id"],
            "college_id": college.json()["id"],
            "full_name": "North Campus Reviewer",
            "email": "north-reviewer@example.com",
        },
    )
    assert created.status_code == 201, created.text
    reviewer = created.json()["reviewer"]
    assert reviewer["college_id"] == college.json()["id"]
    assert reviewer["college_name"] == "North Campus"
    assert reviewer["username"] == "ABC001-NORTH"
    reviewer_login = client.post(
        "/api/auth/login",
        json={"username": reviewer["username"], "password": created.json()["temporary_password"]},
    )
    assert reviewer_login.status_code == 200
    assert reviewer_login.json()["user"]["college_name"] == "North Campus"
    assert reviewer_login.json()["user"]["college_id"] == college.json()["id"]

    duplicate = client.post(
        "/api/reviewers",
        headers=headers,
        json={
            "university_id": university["id"],
            "college_id": college.json()["id"],
            "full_name": "Another Reviewer",
            "email": "another-reviewer@example.com",
        },
    )
    assert duplicate.status_code == 409
    programme = client.post(
        "/api/programmes",
        headers=headers,
        json={
            "university_id": university["id"],
            "college_id": college.json()["id"],
            "name": "North Campus Programme",
            "degree_type": "BSc",
            "level": "ug",
            "duration_years": "1",
            "semester_count": 2,
            "academic_year": "2028-2029",
        },
    )
    assert programme.status_code == 201, programme.text
    assert programme.json()["college_name"] == "North Campus"
    college_detail = client.get("/api/colleges", headers=headers).json()[0]
    assert college_detail["reviewer_id"] == reviewer["id"]
    assert college_detail["programme_count"] == 1


def test_ai_curriculum_generation_is_grounded_editable_and_deterministically_checked(client, monkeypatch):
    from app.schemas import GeneratedCurriculumContent

    headers = regulatory_admin_headers(client)
    source = upload_regulatory_pdf(client, headers, "Verified Curriculum Credit Rule").json()
    rule = next(
        item
        for item in client.get(
            "/api/regulatory-rules",
            headers=headers,
            params={"document_id": source["id"], "verification_status": "pending"},
        ).json()
        if "120 credits" in item["text"]
    )
    assert client.patch(
        f"/api/regulatory-rules/{rule['id']}/verification",
        headers=headers,
        json={"verification_status": "verified"},
    ).status_code == 200
    assert client.put(
        f"/api/regulatory-rules/{rule['id']}/credit-constraint",
        headers=headers,
        json={"kind": "min_total_credits", "value": "120"},
    ).status_code == 200

    university = client.get("/api/universities", headers=headers, params={"search": "ABC"}).json()[0]
    programme = client.post(
        "/api/programmes",
        headers=headers,
        json={
            "university_id": university["id"],
            "name": "B.Sc. Example Programme",
            "degree_type": "B.Sc.",
            "level": "ug",
            "duration_years": 2,
            "semester_count": 2,
            "academic_year": "2027-2028",
            "regulatory_document_ids": [source["id"]],
        },
    ).json()

    generated_payload = {
        "programme_overview": "A complete two-semester programme draft for review.",
        "programme_educational_objectives": ["Prepare graduates for professional practice."],
        "programme_outcomes": [{"code": "PO1", "statement": "Apply foundational programme knowledge."}],
        "programme_specific_outcomes": [{"code": "PSO1", "statement": "Apply discipline-specific methods."}],
        "semesters": [
            {
                "semester_number": semester,
                "title": f"Semester {semester}",
                "courses": [
                    {
                        "course_code": f"EX{semester}01",
                        "title": f"Example course {semester}",
                        "category": "Core",
                        "credits": 60,
                        "description": "A substantive course description for this course.",
                        "learning_objectives": ["Understand foundational concepts."],
                        "course_outcomes": [{"code": f"CO{semester}1", "statement": "Explain core concepts clearly."}],
                        "units": [{"unit_number": 1, "title": "Foundations", "topics": ["Core concepts"]}],
                        "teaching_methods": ["Lectures"],
                        "assessment_methods": ["Assignments"],
                        "learning_resources": ["Example textbook"],
                    }
                ],
            }
            for semester in (1, 2)
        ],
        "co_po_mapping": [
            {"course_code": f"EX{semester}01", "course_outcome_code": f"CO{semester}1", "programme_outcome_codes": ["PO1"]}
            for semester in (1, 2)
        ],
        "co_pso_mapping": [
            {"course_code": f"EX{semester}01", "course_outcome_code": f"CO{semester}1", "programme_outcome_codes": ["PSO1"]}
            for semester in (1, 2)
        ],
        "regulatory_references": [{"rule_id": rule["id"], "application": "Used as the source for the credit check."}],
    }

    async def fake_openai_generation(*, model, programme, evidence):
        assert programme["programme_name"] == "B.Sc. Example Programme"
        assert evidence[0]["rule_id"] == rule["id"]
        return GeneratedCurriculumContent.model_validate(generated_payload)

    monkeypatch.setattr("app.config.settings.openai_api_key", "test-api-key")
    monkeypatch.setattr(
        "app.routers.ai_generation.generate_curriculum_with_openai",
        fake_openai_generation,
    )
    response = client.post(f"/api/ai-generation/programmes/{programme['id']}", headers=headers)
    assert response.status_code == 201, response.text
    generated = response.json()
    assert generated["status"] == "completed"
    assert generated["curriculum"]["credit_distribution"] == [
        {"semester_number": 1, "credits": "60"},
        {"semester_number": 2, "credits": "60"},
    ]
    assert generated["validation_status"] == "passed"
    assert generated["regulatory_references"][0]["rule_id"] == rule["id"]
    assert generated["regulatory_references"][0]["text"] == rule["text"]

    edited_payload = generated["curriculum"]
    edited_payload["semesters"][0]["courses"][0]["credits"] = "50"
    edited = client.patch(
        f"/api/ai-generation/{generated['id']}",
        headers=headers,
        json=edited_payload,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["curriculum"]["credit_distribution"][0]["credits"] == "50"
    assert edited.json()["validation_status"] == "failed"
    invalid_citation = edited.json()["curriculum"]
    invalid_citation["regulatory_references"][0]["rule_id"] = "00000000-0000-0000-0000-000000000000"
    rejected_edit = client.patch(
        f"/api/ai-generation/{generated['id']}",
        headers=headers,
        json=invalid_citation,
    )
    assert rejected_edit.status_code == 422
    dashboard = client.get("/api/admin/dashboard", headers=headers)
    assert dashboard.json()["total_curricula"] == 1
    history = client.get(
        f"/api/ai-generation/programmes/{programme['id']}",
        headers=headers,
    )
    assert history.status_code == 200
    assert history.json()[0]["id"] == generated["id"]

    reviewer = client.post(
        "/api/auth/login",
        json={"email": "reviewer@example.com", "password": "reviewer-test-password"},
    )
    assert client.get(
        f"/api/ai-generation/{generated['id']}",
        headers={"Authorization": f"Bearer {reviewer.json()['access_token']}"},
    ).status_code == 403


def test_ai_curriculum_generation_requires_backend_openai_configuration(client, monkeypatch):
    headers = regulatory_admin_headers(client)
    monkeypatch.setattr("app.config.settings.openai_api_key", None)
    response = client.post(
        "/api/ai-generation/programmes/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_curriculum_library_versions_exports_and_university_scoped_publishing(client, monkeypatch):
    from io import BytesIO

    import pymupdf
    from docx import Document as WordDocument
    from app.schemas import GeneratedCurriculumContent

    headers = regulatory_admin_headers(client)
    source = upload_regulatory_pdf(client, headers, "Library Verified Credit Rule").json()
    rule = next(
        item
        for item in client.get(
            "/api/regulatory-rules",
            headers=headers,
            params={"document_id": source["id"], "verification_status": "pending"},
        ).json()
        if "120 credits" in item["text"]
    )
    assert client.patch(
        f"/api/regulatory-rules/{rule['id']}/verification",
        headers=headers,
        json={"verification_status": "verified"},
    ).status_code == 200
    assert client.put(
        f"/api/regulatory-rules/{rule['id']}/credit-constraint",
        headers=headers,
        json={"kind": "min_total_credits", "value": "120"},
    ).status_code == 200
    university = client.get("/api/universities", headers=headers, params={"search": "ABC"}).json()[0]
    programme = client.post(
        "/api/programmes",
        headers=headers,
        json={
            "university_id": university["id"],
            "name": "B.A. Library Test",
            "degree_type": "B.A.",
            "level": "ug",
            "duration_years": 1,
            "semester_count": 1,
            "academic_year": "2027-2028",
            "regulatory_document_ids": [source["id"]],
        },
    ).json()
    generated_payload = {
        "programme_overview": "A complete one-semester programme draft prepared for library review.",
        "programme_educational_objectives": ["Prepare learners for advanced academic study."],
        "programme_outcomes": [{"code": "PO1", "statement": "Apply foundational academic knowledge."}],
        "programme_specific_outcomes": [{"code": "PSO1", "statement": "Apply subject-specific learning methods."}],
        "semesters": [{
            "semester_number": 1,
            "title": "Foundation semester",
            "courses": [{
                "course_code": "LIB101",
                "title": "Foundations",
                "category": "Core",
                "credits": 120,
                "description": "A substantive foundation course for this sample programme.",
                "learning_objectives": ["Understand key academic foundations."],
                "course_outcomes": [{"code": "CO1", "statement": "Explain foundational academic concepts."}],
                "units": [{"unit_number": 1, "title": "Core foundations", "topics": ["Core concepts"]}],
                "teaching_methods": ["Seminar"],
                "assessment_methods": ["Research assignment"],
                "learning_resources": ["Sample academic text"],
            }],
        }],
        "co_po_mapping": [{"course_code": "LIB101", "course_outcome_code": "CO1", "programme_outcome_codes": ["PO1"]}],
        "co_pso_mapping": [{"course_code": "LIB101", "course_outcome_code": "CO1", "programme_outcome_codes": ["PSO1"]}],
        "regulatory_references": [{"rule_id": rule["id"], "application": "Used as the evidence for the configured credit check."}],
    }

    async def fake_openai_generation(*, model, programme, evidence):
        return GeneratedCurriculumContent.model_validate(generated_payload)

    monkeypatch.setattr("app.config.settings.openai_api_key", "test-api-key")
    monkeypatch.setattr("app.routers.ai_generation.generate_curriculum_with_openai", fake_openai_generation)
    generation = client.post(f"/api/ai-generation/programmes/{programme['id']}", headers=headers)
    assert generation.status_code == 201, generation.text
    generation_job = generation.json()

    created = client.post(
        "/api/curricula",
        headers=headers,
        json={"generation_job_id": generation_job["id"], "title": "Library test curriculum"},
    )
    assert created.status_code == 201, created.text
    curriculum = created.json()
    assert curriculum["status"] == "draft"
    assert curriculum["current_version_number"] == 1
    assert curriculum["generation_job_id"] == generation_job["id"]
    assert client.post(
        "/api/curricula",
        headers=headers,
        json={"generation_job_id": generation_job["id"]},
    ).status_code == 409

    for file_format, expected_content_type, expected_prefix in (
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK"),
        ("pdf", "application/pdf", b"%PDF-"),
    ):
        export = client.get(
            f"/api/curricula/{curriculum['id']}/versions/1/export",
            headers=headers,
            params={"format": file_format},
        )
        assert export.status_code == 200, export.text
        assert export.headers["content-type"] == expected_content_type
        assert export.content.startswith(expected_prefix)
        if file_format == "docx":
            exported_document = WordDocument(BytesIO(export.content))
            exported_text = "\n".join(paragraph.text for paragraph in exported_document.paragraphs)
        else:
            with pymupdf.open(stream=export.content, filetype="pdf") as exported_document:
                exported_text = "\n".join(page.get_text() for page in exported_document)
        assert "Library test curriculum" in exported_text
        assert "Foundations" in exported_text
        assert "Library Verified Credit Rule" in exported_text

    edited_content = curriculum["current_version"]["content"]
    edited_content["semesters"][0]["courses"][0]["title"] = "Updated foundations"
    edited = client.patch(
        f"/api/curricula/{curriculum['id']}",
        headers=headers,
        json={"content": edited_content},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["current_version_number"] == 2
    history = client.get(f"/api/curricula/{curriculum['id']}/versions", headers=headers)
    assert [version["version_number"] for version in history.json()] == [1, 2]
    assert history.json()[0]["content"]["semesters"][0]["courses"][0]["title"] == "Foundations"
    filtered = client.get("/api/curricula", headers=headers, params={"search": "Library test"})
    assert filtered.status_code == 200
    assert filtered.json()[0]["id"] == curriculum["id"]

    foreign_university = client.post(
        "/api/universities",
        headers=headers,
        json={"name": "Foreign Review University", "code": "FRU001"},
    ).json()
    foreign_reviewer = client.post(
        "/api/reviewers",
        headers=headers,
        json={
            "university_id": foreign_university["id"],
            "full_name": "Foreign Reviewer",
            "email": "foreign-reviewer@example.com",
        },
    )
    assert foreign_reviewer.status_code == 201, foreign_reviewer.text

    reviewer_login = client.post(
        "/api/auth/login",
        json={"email": "reviewer@example.com", "password": "reviewer-test-password"},
    )
    reviewer_headers = {"Authorization": f"Bearer {reviewer_login.json()['access_token']}"}
    changed = client.post(
        "/api/auth/change-password",
        headers=reviewer_headers,
        json={
            "current_password": "reviewer-test-password",
            "new_password": "reviewer-updated-strong-password",
        },
    )
    assert changed.status_code == 200

    published = client.post(
        f"/api/curricula/{curriculum['id']}/publish",
        headers=headers,
        json={"reviewer_id": reviewer_login.json()["user"]["id"], "deadline": "2028-01-15"},
    )
    assert published.status_code == 201, published.text
    assignment = published.json()["assignment"]
    assert assignment["status"] == "pending"
    assert assignment["version_number"] == 2
    assert assignment["validation_status"] == "passed"
    notifications = client.get("/api/curricula/reviewer/notifications", headers=reviewer_headers)
    assert notifications.status_code == 200
    assert notifications.json()[0]["assignment_id"] == assignment["id"]
    marked_read = client.post(
        f"/api/curricula/reviewer/notifications/{notifications.json()[0]['id']}/read",
        headers=reviewer_headers,
    )
    assert marked_read.status_code == 200
    assert marked_read.json()["read_at"]

    reviewer_assignments = client.get("/api/curricula/reviewer/assignments", headers=reviewer_headers)
    assert reviewer_assignments.status_code == 200
    assert [item["id"] for item in reviewer_assignments.json()] == [assignment["id"]]
    reviewer_download = client.get(
        f"/api/curricula/reviewer/assignments/{assignment['id']}/download",
        headers=reviewer_headers,
        params={"format": "pdf"},
    )
    assert reviewer_download.status_code == 200
    assert reviewer_download.content.startswith(b"%PDF-")

    review_detail = client.get(
        f"/api/reviews/assignments/{assignment['id']}",
        headers=reviewer_headers,
    )
    assert review_detail.status_code == 200, review_detail.text
    assert review_detail.json()["assignment"]["status"] == "under_review"
    assert review_detail.json()["curriculum_content"]["programme_overview"]
    assert client.get("/api/reviews/assignments", headers=reviewer_headers).status_code == 403

    saved_draft = client.post(
        f"/api/reviews/assignments/{assignment['id']}/comments",
        headers=reviewer_headers,
        json={
            "body": "Draft note on the course.",
            "section_path": "Semester 1 / Foundations / Course Outcomes",
            "priority": "high",
            "is_submitted": False,
        },
    )
    assert saved_draft.status_code == 201, saved_draft.text
    blocked_decision = client.post(
        f"/api/reviews/assignments/{assignment['id']}/submit",
        headers=reviewer_headers,
        json={"decision": "revision_requested"},
    )
    assert blocked_decision.status_code == 409
    submitted_comment = client.patch(
        f"/api/reviews/comments/{saved_draft.json()['id']}",
        headers=reviewer_headers,
        json={
            "body": "Please update the foundations section to clarify the expected learning outcomes.",
            "is_submitted": True,
        },
    )
    assert submitted_comment.status_code == 200, submitted_comment.text
    comment = submitted_comment.json()
    assert comment["status"] == "open"
    assert comment["version_number"] == 2

    from io import BytesIO

    from docx import Document

    correction = Document()
    correction.add_paragraph("Reviewer annotated correction for version 2.")
    correction_bytes = BytesIO()
    correction.save(correction_bytes)
    uploaded_document = client.post(
        f"/api/reviews/assignments/{assignment['id']}/documents",
        headers=reviewer_headers,
        files={
            "file": (
                "annotated-curriculum.docx",
                correction_bytes.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert uploaded_document.status_code == 201, uploaded_document.text
    uploaded_document_id = uploaded_document.json()["id"]
    secured_download = client.get(
        f"/api/reviews/documents/{uploaded_document_id}/download",
        headers=reviewer_headers,
    )
    assert secured_download.status_code == 200
    assert secured_download.content.startswith(b"PK")

    requested = client.post(
        f"/api/reviews/assignments/{assignment['id']}/submit",
        headers=reviewer_headers,
        json={"decision": "revision_requested", "message": "Please address the high-priority feedback."},
    )
    assert requested.status_code == 200, requested.text
    assert requested.json()["assignment"]["status"] == "revision_requested"
    assert client.post(
        f"/api/reviews/assignments/{assignment['id']}/submit",
        headers=reviewer_headers,
        json={"decision": "reviewer_rejected"},
    ).status_code == 422
    assert client.post(
        f"/api/reviews/admin/assignments/{assignment['id']}/final-decision",
        headers=headers,
        json={"decision": "rejected"},
    ).status_code == 422
    assert client.post(
        f"/api/reviews/admin/assignments/{assignment['id']}/final-decision",
        headers=headers,
        json={"decision": "approved"},
    ).status_code == 409
    admin_feedback = client.get("/api/reviews/assignments", headers=headers, params={"status": "revision_requested"})
    assert admin_feedback.status_code == 200, admin_feedback.text
    feedback = next(item for item in admin_feedback.json() if item["assignment"]["id"] == assignment["id"])
    assert feedback["comments"][0]["body"] == comment["body"]
    assert feedback["documents"][0]["id"] == uploaded_document_id

    reply = client.post(
        f"/api/reviews/comments/{comment['id']}/replies",
        headers=headers,
        json={"body": "We will update the course outcomes in the next version."},
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["author_role"] == "admin"
    resolved = client.patch(
        f"/api/reviews/comments/{comment['id']}/status",
        headers=headers,
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"
    reviewer_history_view = client.get(
        f"/api/reviews/assignments/{assignment['id']}",
        headers=reviewer_headers,
    )
    assert reviewer_history_view.status_code == 200, reviewer_history_view.text
    assert reviewer_history_view.json()["comments"][0]["replies"][0]["body"] == reply.json()["body"]

    updated_content = edited.json()["current_version"]["content"]
    updated_content["programme_overview"] = "A revised two-semester programme draft that incorporates reviewer feedback."
    revised = client.patch(
        f"/api/curricula/{curriculum['id']}",
        headers=headers,
        json={"content": updated_content},
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["current_version_number"] == 3
    comparison = client.get(
        f"/api/reviews/curricula/{curriculum['id']}/compare",
        headers=headers,
        params={"from_version": 2, "to_version": 3},
    )
    assert comparison.status_code == 200, comparison.text
    assert any(change["path"] == "programme_overview" for change in comparison.json()["changes"])

    republished = client.post(
        f"/api/curricula/{curriculum['id']}/publish",
        headers=headers,
        json={"reviewer_id": reviewer_login.json()["user"]["id"]},
    )
    assert republished.status_code == 201, republished.text
    revised_assignment = republished.json()["assignment"]
    assert revised_assignment["version_number"] == 3
    assert revised_assignment["id"] != assignment["id"]
    admin_revision = WordDocument()
    admin_revision.add_paragraph("Updated administrator curriculum export.")
    admin_revision_bytes = BytesIO()
    admin_revision.save(admin_revision_bytes)
    admin_document = client.post(
        f"/api/reviews/admin/assignments/{revised_assignment['id']}/documents",
        headers=headers,
        files={
            "file": (
                "revised-curriculum.docx",
                admin_revision_bytes.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert admin_document.status_code == 201, admin_document.text
    assert admin_document.json()["uploader_name"] == "Platform Admin"
    assert client.get(
        f"/api/reviews/assignments/{revised_assignment['id']}",
        headers=reviewer_headers,
    ).status_code == 200
    revised_review = client.get(
        f"/api/reviews/assignments/{revised_assignment['id']}",
        headers=reviewer_headers,
    )
    assert any(item["id"] == admin_document.json()["id"] for item in revised_review.json()["documents"])
    assert client.get(
        f"/api/reviews/documents/{admin_document.json()['id']}/download",
        headers=reviewer_headers,
    ).status_code == 200
    approved = client.post(
        f"/api/reviews/assignments/{revised_assignment['id']}/submit",
        headers=reviewer_headers,
        json={"decision": "reviewer_recommended", "message": "The revised curriculum is recommended for final approval."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["assignment"]["status"] == "reviewer_recommended"
    assert client.post(
        f"/api/reviews/admin/assignments/{revised_assignment['id']}/final-decision",
        headers=reviewer_headers,
        json={"decision": "approved"},
    ).status_code == 403
    final_approval = client.post(
        f"/api/reviews/admin/assignments/{revised_assignment['id']}/final-decision",
        headers=headers,
        json={"decision": "approved"},
    )
    assert final_approval.status_code == 200, final_approval.text
    assert final_approval.json()["assignment"]["status"] == "approved"
    original_assignment = client.get(
        f"/api/reviews/assignments?status=revision_requested",
        headers=headers,
    )
    assert original_assignment.status_code == 200
    assert any(item["assignment"]["id"] == assignment["id"] for item in original_assignment.json())
    admin_notifications = client.get("/api/curricula/reviewer/notifications", headers=headers)
    assert admin_notifications.status_code == 200
    assert any(item["title"] == "Curriculum review completed" for item in admin_notifications.json())

    archived = client.post(f"/api/curricula/{curriculum['id']}/archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert client.patch(
        f"/api/curricula/{curriculum['id']}",
        headers=headers,
        json={"title": "Should not edit archived item"},
    ).status_code == 409
    assert client.get(
        f"/api/curricula/reviewer/assignments/{assignment['id']}/download",
        headers=reviewer_headers,
        params={"format": "pdf"},
    ).status_code == 200

    foreign_login = client.post(
        "/api/auth/login",
        json={"email": "foreign-reviewer@example.com", "password": foreign_reviewer.json()["temporary_password"]},
    )
    foreign_headers = {"Authorization": f"Bearer {foreign_login.json()['access_token']}"}
    foreign_changed = client.post(
        "/api/auth/change-password",
        headers=foreign_headers,
        json={
            "current_password": foreign_reviewer.json()["temporary_password"],
            "new_password": "foreign-updated-strong-password",
        },
    )
    assert foreign_changed.status_code == 200
    assert client.get(
        f"/api/reviews/assignments/{assignment['id']}",
        headers=foreign_headers,
    ).status_code == 404
    assert client.get(
        f"/api/reviews/documents/{uploaded_document_id}/download",
        headers=foreign_headers,
    ).status_code == 404
    assert client.get("/api/curricula/reviewer/assignments", headers=foreign_headers).json() == []
    assert client.get("/api/curricula/reviewer/notifications", headers=foreign_headers).json() == []
    assert client.get(
        f"/api/curricula/reviewer/assignments/{assignment['id']}/download",
        headers=foreign_headers,
        params={"format": "pdf"},
    ).status_code == 404


def test_programme_rejects_foreign_university_regulations_and_duplicate_year(client):
    headers = regulatory_admin_headers(client)
    university_response = client.post(
        "/api/universities",
        headers=headers,
        json={"name": "XYZ University", "code": "XYZ001"},
    )
    assert university_response.status_code == 201
    xyz = university_response.json()
    abc = client.get("/api/universities", headers=headers, params={"search": "ABC"}).json()[0]
    source_response = client.post(
        "/api/regulations",
        headers=headers,
        data={
            "category": "university",
            "title": "ABC University regulations",
            "issuing_authority": "ABC University",
            "version": "2027",
            "applicability": "Undergraduate programmes",
            "university_id": abc["id"],
        },
        files={
            "file": (
                "abc-university.pdf",
                sample_regulatory_pdf("Students shall follow the approved academic regulations."),
                "application/pdf",
            )
        },
    )
    assert source_response.status_code == 201, source_response.text
    source_id = source_response.json()["id"]
    same_title_other_university = client.post(
        "/api/regulations",
        headers=headers,
        data={
            "category": "university",
            "title": "ABC University regulations",
            "issuing_authority": "XYZ University",
            "version": "2027",
            "applicability": "Undergraduate programmes",
            "university_id": xyz["id"],
        },
        files={
            "file": (
                "xyz-university.pdf",
                sample_regulatory_pdf("Students shall follow the approved academic regulations."),
                "application/pdf",
            )
        },
    )
    assert same_title_other_university.status_code == 201, same_title_other_university.text
    foreign_programme = client.post(
        "/api/programmes",
        headers=headers,
        json={
            "university_id": xyz["id"],
            "name": "B.Sc. Biology",
            "degree_type": "B.Sc.",
            "level": "ug",
            "duration_years": "3",
            "semester_count": 6,
            "academic_year": "2027-2028",
            "regulatory_document_ids": [source_id],
        },
    )
    assert foreign_programme.status_code == 403

    programme_data = {
        "university_id": abc["id"],
        "name": "B.Sc. Biology",
        "degree_type": "B.Sc.",
        "level": "ug",
        "duration_years": "3",
        "semester_count": 6,
        "academic_year": "2027-2028",
        "regulatory_document_ids": [source_id],
    }
    created = client.post("/api/programmes", headers=headers, json=programme_data)
    assert created.status_code == 201
    duplicate = client.post("/api/programmes", headers=headers, json=programme_data)
    assert duplicate.status_code == 409
    updated = client.patch(
        f"/api/programmes/{created.json()['id']}",
        headers=headers,
        json={"academic_year": "2028-2029", "status": "inactive"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "inactive"
    assert client.get("/api/programmes", headers=headers, params={"university_id": xyz["id"]}).json() == []


def test_credit_constraint_requires_verified_rule_and_active_unconflicted_source(client):
    headers = regulatory_admin_headers(client)
    document = upload_regulatory_pdf(client, headers, "Rule verification gate").json()
    rule = client.get(
        "/api/regulatory-rules",
        headers=headers,
        params={"document_id": document["id"]},
    ).json()[0]
    pending = client.put(
        f"/api/regulatory-rules/{rule['id']}/credit-constraint",
        headers=headers,
        json={"kind": "max_total_credits", "value": 150},
    )
    assert pending.status_code == 409


def test_regulatory_conflict_archival_and_duplicate_version(client):
    headers = regulatory_admin_headers(client)
    uploaded = upload_regulatory_pdf(client, headers, "NEP credit guidance")
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    rule = client.get(
        "/api/regulatory-rules",
        headers=headers,
        params={"document_id": document["id"]},
    ).json()[0]
    verified = client.patch(
        f"/api/regulatory-rules/{rule['id']}/verification",
        headers=headers,
        json={"verification_status": "verified"},
    )
    assert verified.status_code == 200

    invalid_conflict = client.patch(
        f"/api/regulatory-rules/{rule['id']}/conflict",
        headers=headers,
        json={"has_conflict": True},
    )
    assert invalid_conflict.status_code == 422
    flagged = client.patch(
        f"/api/regulatory-rules/{rule['id']}/conflict",
        headers=headers,
        json={"has_conflict": True, "conflict_note": "Check for a later superseding rule"},
    )
    assert flagged.status_code == 200
    assert flagged.json()["has_conflict"] is True
    conflicts = client.get("/api/regulatory-rules", headers=headers, params={"conflicts_only": True})
    assert [item["id"] for item in conflicts.json()] == [rule["id"]]
    retrieval = client.post(
        "/api/regulatory-rules/retrieve",
        headers=headers,
        json={"query": "approved programme credits"},
    )
    assert all(item["rule_id"] != rule["id"] for item in retrieval.json())

    duplicate = upload_regulatory_pdf(client, headers, "NEP credit guidance")
    assert duplicate.status_code == 409
    archived = client.post(f"/api/regulations/{document['id']}/archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert client.patch(
        f"/api/regulatory-rules/{rule['id']}/verification",
        headers=headers,
        json={"verification_status": "rejected"},
    ).status_code == 409


def test_invalid_regulatory_uploads_and_role_access(client):
    reviewer_login = client.post(
        "/api/auth/login",
        json={"email": "reviewer@example.com", "password": "reviewer-test-password"},
    )
    reviewer_headers = {"Authorization": f"Bearer {reviewer_login.json()['access_token']}"}
    denied = client.get("/api/regulations", headers=reviewer_headers)
    assert denied.status_code == 403

    headers = regulatory_admin_headers(client)
    invalid = client.post(
        "/api/regulations",
        headers=headers,
        data={
            "category": "ugc",
            "issuing_authority": "UGC",
            "version": "1",
            "applicability": "Higher education",
        },
        files={"file": ("invalid.pdf", b"not a PDF", "application/pdf")},
    )
    assert invalid.status_code == 422


def test_regulatory_docx_extracts_paragraphs_and_tables(client):
    from io import BytesIO

    docx = WordDocument()
    docx.add_paragraph("Section 2.4: Institutions must publish the approved academic regulations.")
    table = docx.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Requirement"
    table.cell(0, 1).text = "Credits"
    table.cell(1, 0).text = "Programme minimum"
    table.cell(1, 1).text = "120 credits"
    data = BytesIO()
    docx.save(data)

    response = client.post(
        "/api/regulations",
        headers=regulatory_admin_headers(client),
        data={
            "category": "university",
            "title": "Academic Regulations",
            "issuing_authority": "ABC University",
            "version": "2026",
            "applicability": "All undergraduate programmes",
            "university_id": str(
                client.get("/api/universities", headers=regulatory_admin_headers(client)).json()[0]["id"]
            ),
        },
        files={
            "file": (
                "academic-regulations.docx",
                data.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["page_count"] == 0
    assert response.json()["extraction_warnings"]
    text_response = client.get(
        f"/api/regulations/{response.json()['id']}/text",
        headers=regulatory_admin_headers(client),
    )
    assert "120 credits" in text_response.json()["extracted_text"]
