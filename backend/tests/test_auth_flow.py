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
    monkeypatch.setattr(settings, "review_storage_dir", tmp_path / "reviews")
    monkeypatch.setattr(settings, "regulatory_storage_dir", tmp_path / "regulations")
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
    invalid_password = client.post(
        "/api/reviewers",
        headers=headers,
        json={
            "university_id": university["id"],
            "full_name": "XYZ Reviewer",
            "email": "xyz-reviewer@example.com",
            "password": "short",
        },
    )
    assert invalid_password.status_code == 422

    created = client.post(
        "/api/reviewers",
        headers=headers,
        json={
            "university_id": university["id"],
            "full_name": "XYZ Reviewer",
            "email": "xyz-reviewer@example.com",
            "password": "xyz-reviewer-password",
        },
    )
    assert created.status_code == 201
    reviewer = created.json()
    assert reviewer["must_change_password"] is False
    assert reviewer["username"] == "XYZ001"
    assert "temporary_password" not in reviewer

    duplicate = client.post(
        "/api/reviewers",
        headers=headers,
        json={
            "university_id": university["id"],
            "full_name": "Second Reviewer",
            "email": "second-reviewer@example.com",
            "password": "second-reviewer-password",
        },
    )
    assert duplicate.status_code == 409

    reviewer_id = reviewer["id"]
    username_login = client.post(
        "/api/auth/login",
        json={"username": "xyz001", "password": "xyz-reviewer-password"},
    )
    assert username_login.status_code == 200
    assert username_login.json()["user"]["username"] == "XYZ001"
    assert username_login.json()["user"]["must_change_password"] is False

    updated = client.patch(
        f"/api/reviewers/{reviewer_id}",
        headers=headers,
        json={"full_name": "Updated XYZ Reviewer"},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Updated XYZ Reviewer"

    reset = client.post(
        f"/api/reviewers/{reviewer_id}/reset-password",
        headers=headers,
        json={"password": "xyz-reviewer-reset-password"},
    )
    assert reset.status_code == 200
    assert reset.json()["must_change_password"] is False
    assert "password" not in reset.json()
    invalid_reset = client.post(
        f"/api/reviewers/{reviewer_id}/reset-password",
        headers=headers,
        json={"password": "short"},
    )
    assert invalid_reset.status_code == 422
    old_password_login = client.post(
        "/api/auth/login",
        json={"email": "xyz-reviewer@example.com", "password": "xyz-reviewer-password"},
    )
    assert old_password_login.status_code == 401
    new_password_login = client.post(
        "/api/auth/login",
        json={"email": "xyz-reviewer@example.com", "password": "xyz-reviewer-reset-password"},
    )
    assert new_password_login.status_code == 200
    assert new_password_login.json()["user"]["must_change_password"] is False


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
            "password": "north-reviewer-password",
        },
    )
    assert created.status_code == 201, created.text
    reviewer = created.json()
    assert reviewer["college_id"] == college.json()["id"]
    assert reviewer["college_name"] == "North Campus"
    assert reviewer["username"] == "ABC001-NORTH"
    reviewer_login = client.post(
        "/api/auth/login",
        json={"username": reviewer["username"], "password": "north-reviewer-password"},
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
            "password": "another-reviewer-password",
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




def test_ai_curriculum_generation_requires_backend_openai_configuration(client, monkeypatch):
    headers = admin_headers(client)
    monkeypatch.setattr("app.config.settings.openai_api_key", None)
    response = client.post(
        "/api/ai-generation/programmes/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_regulatory_course_flow_and_manual_curriculum_structure(client):
    headers = admin_headers(client)
    assert client.get("/api/regulations", headers=headers).status_code == 200
    assert client.get("/api/regulatory-rules", headers=headers).status_code == 200
    assert client.get("/api/courses", headers=headers).status_code == 200
    assert client.get("/api/credit-table", headers=headers).status_code == 200

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
    assert "applicable_regulations" not in programme

    content = {
        "semesters": [
            {"semester_number": 1, "courses": [{
                "course_code": "MD101", "name": "Design Foundations", "category": "Major",
                "course_type": "theory", "credits": "3",
            }]},
            {"semester_number": 2, "courses": [{
                "course_code": "MD102", "name": "Applied Design", "category": "Major",
                "course_type": "practical", "credits": "4",
            }]},
        ],
    }
    created = client.post(
        "/api/curriculum-structures",
        headers=headers,
        json={"programme_id": programme["id"], "title": "Manual curriculum", "content": content},
    )
    assert created.status_code == 201, created.text
    structure = created.json()
    assert structure["version"]["content"]["semesters"][0]["courses"][0]["course_code"] == "MD101"
    assert structure["version"]["content"]["semesters"][1]["courses"][0]["credits"] == "4"
    assert client.post(f"/api/curriculum-structures/{structure['id']}/validate", headers=headers).status_code == 404


def test_regulation_rule_credit_table_and_course_library_flow(client):
    headers = admin_headers(client)
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "A minimum of 12 credits in Professional Core category is required.")
    pdf_bytes = pdf.tobytes()
    pdf.close()

    uploaded = client.post(
        "/api/regulations",
        headers=headers,
        data={
            "title": "Undergraduate Credit Rules",
            "issuing_authority": "Academic Board",
            "year": "2026",
            "version": "1.0",
            "programme_level": "ug",
        },
        files={"file": ("credit-rules.pdf", pdf_bytes, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["rule_count"] == 1
    assert document["courses_imported"] == 0

    rules = client.get(
        "/api/regulatory-rules",
        headers=headers,
        params={"document_id": document["id"]},
    )
    assert rules.status_code == 200
    rule = rules.json()[0]
    assert rule["status"] == "applied"
    assert rule["rule_type"] == "category_min"
    assert rule["category"] == "Professional Core"
    assert rule["value"] == "12.00"
    searched_rules = client.get(
        "/api/regulatory-rules",
        headers=headers,
        params={"document_id": document["id"], "search": "Professional Core", "status": "applied"},
    )
    assert searched_rules.status_code == 200
    assert [item["id"] for item in searched_rules.json()] == [rule["id"]]
    table = client.get("/api/credit-table", headers=headers, params={"programme_level": "ug"})
    assert table.json()["rows"] == []

    edited = client.patch(
        f"/api/regulatory-rules/{rule['id']}",
        headers=headers,
        json={
            "text": "A minimum of 12 credits in Professional Core category is required for every programme.",
            "rule_type": "category_min",
            "category": "Professional Core",
            "semester": None,
            "value": "12",
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "applied"
    table = client.get("/api/credit-table", headers=headers, params={"programme_level": "ug"})
    assert table.json()["rows"] == []

    created = client.post(
        "/api/courses",
        headers=headers,
        json={
            "course_code": "PC101",
            "name": "Professional Core Foundations",
            "category": "Professional Core",
            "semester": 1,
            "lecture_hours": "2",
            "tutorial_hours": "1",
            "practical_hours": "0",
            "credits": "11",
        },
    )
    assert created.status_code == 201, created.text
    summary = client.get("/api/courses/summary", headers=headers, params={"programme_level": "ug"})
    category_summary = next(row for row in summary.json()["categories"] if row["category"] == "Professional Core")
    assert category_summary["status"] == "outside_limit"

    imported = client.post(
        "/api/courses/import",
        headers=headers,
        files={
            "file": (
                "courses.csv",
                "course_code,name,category,semester,lecture_hours,tutorial_hours,practical_hours,credits\nPC102,Professional Core Practice,Professional Core,1,1,0,1,1\n",
                "text/csv",
            )
        },
    )
    assert imported.status_code == 200, imported.text
    assert imported.json() == {"imported": 1, "errors": []}
    summary = client.get("/api/courses/summary", headers=headers, params={"programme_level": "ug"})
    category_summary = next(row for row in summary.json()["categories"] if row["category"] == "Professional Core")
    assert category_summary["used_credits"] == "12.00"
    assert category_summary["status"] == "within_limit"

    overridden = client.put(
        "/api/credit-table/overrides",
        headers=headers,
        json={
            "programme_level": "ug",
            "scope_type": "category",
            "category": "Professional Core",
            "limit_type": "minimum",
            "value": "13",
        },
    )
    assert overridden.status_code == 422, overridden.text
    assert client.get("/api/courses/summary", headers=headers, params={"programme_level": "ug"}).json()["categories"][0]["status"] == "within_limit"

    stored_pdfs = list(settings.regulatory_storage_dir.glob("*.pdf"))
    assert len(stored_pdfs) == 1
    stored_pdf = stored_pdfs[0]
    assert stored_pdf.is_file()
    deleted = client.delete(f"/api/regulations/{document['id']}", headers=headers)
    assert deleted.status_code == 204
    assert not stored_pdf.exists()
    assert client.get(
        "/api/regulations",
        headers=headers,
        params={"search": "Undergraduate Credit Rules"},
    ).json() == []
    assert client.get(
        "/api/regulatory-rules",
        headers=headers,
        params={"document_id": document["id"]},
    ).json() == []
    assert client.get(
        "/api/credit-table",
        headers=headers,
        params={"programme_level": "ug"},
    ).json()["rows"] == []
    assert client.get(
        f"/api/regulations/{document['id']}/download",
        headers=headers,
    ).status_code == 404


def test_regulation_pdf_imports_complete_course_table_rows_into_library(client):
    headers = admin_headers(client)
    pdf = pymupdf.open()
    page = pdf.new_page()
    column_edges = [30, 120, 310, 400, 460, 520, 565]
    row_edges = [80, 112, 144, 176]
    for x in column_edges:
        page.draw_line((x, row_edges[0]), (x, row_edges[-1]))
    for y in row_edges:
        page.draw_line((column_edges[0], y), (column_edges[-1], y))
    course_rows = [
        ["Course Code", "Course Title", "Category", "Semester", "L-T-P", "Credits"],
        ["CS101", "Foundations of Computing", "Major", "I", "3-1-0", "4"],
        ["", "Applied Computing", "Major", "II", "2-0-2", "3"],
    ]
    for row_index, row in enumerate(course_rows):
        for column_index, value in enumerate(row):
            page.insert_text(
                (column_edges[column_index] + 3, row_edges[row_index] + 21),
                value,
                fontsize=7,
            )
    pdf_bytes = pdf.tobytes()
    pdf.close()

    uploaded = client.post(
        "/api/regulations",
        headers=headers,
        data={
            "title": "Course Table Regulation",
            "issuing_authority": "Academic Board",
            "year": "2026",
            "version": "1.0",
            "programme_level": "ug",
        },
        files={"file": ("course-table.pdf", pdf_bytes, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["courses_imported"] == 2
    assert document["rule_count"] == 0

    listed = client.get("/api/courses", headers=headers).json()
    assert len(listed) == 2
    explicit_code = next(course for course in listed if course["name"] == "Foundations of Computing")
    generated_code = next(course for course in listed if course["name"] == "Applied Computing")
    assert explicit_code["course_code"] == "CS101"
    assert explicit_code["category"] == "Major"
    assert explicit_code["semester"] == 1
    assert explicit_code["lecture_hours"] == "3.00"
    assert explicit_code["tutorial_hours"] == "1.00"
    assert explicit_code["practical_hours"] == "0.00"
    assert explicit_code["credits"] == "4.00"
    assert generated_code["course_code"].startswith("AUTO")
    assert generated_code["semester"] == 2
    assert generated_code["lecture_hours"] == "2.00"
    assert generated_code["tutorial_hours"] == "0.00"
    assert generated_code["practical_hours"] == "2.00"
    assert generated_code["credits"] == "3.00"

    deleted = client.delete(f"/api/regulations/{document['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/courses", headers=headers).json() == []


def test_credit_extraction_classifies_category_totals_without_approval():
    from app.regulatory import extract_credit_rules

    extracted = extract_credit_rules([
        "Major courses may be 4 credits as appropriate.",
        "A minimum of 12 credits in Professional Core category is required.",
        "Credits",
    ])
    assert [(rule["rule_type"], rule["category"], rule["value"]) for rule in extracted] == [
        ("category_total", "Major", 4),
        ("category_min", "Professional Core", 12),
    ]


def test_credit_extraction_reads_minimum_requirement_tables_and_continuation_pages(client):
    from app.regulatory import extract_credit_rules, extract_credit_table_rules, extract_pdf_pages

    pdf = pymupdf.open()
    page = pdf.new_page(width=700, height=300)
    column_edges = [30, 80, 310, 365, 420, 475, 530]
    row_edges = [30, 65, 100, 135, 170, 205]
    for x in column_edges:
        page.draw_line((x, row_edges[0]), (x, row_edges[-1]))
    for y in row_edges:
        page.draw_line((column_edges[0], y), (column_edges[-1], y))
    first_page_rows = [
        ["S. No.", "Broad Category of Course", "", "Minimum Credit Requirement", "", ""],
        ["", "", "", "3-year UG", "", "4-year UG"],
        ["1", "Major (Core)", "60", "", "", "80"],
        ["2", "Minor Stream", "24", "", "", "32"],
        ["3", "Multidisciplinary", "09", "", "", "09"],
    ]
    for row_index, row in enumerate(first_page_rows):
        for column_index, value in enumerate(row):
            if value:
                page.insert_text(
                    (column_edges[column_index] + 3, row_edges[row_index] + 24),
                    value,
                    fontsize=8,
                )
    page.insert_text((30, 250), "A minimum of 160 credits is required for the four-year track.", fontsize=8)

    page = pdf.new_page(width=500, height=180)
    continuation_edges = [30, 80, 310, 400, 490]
    continuation_rows = [
        ["4", "Ability Enhancement Courses (AEC)", "08", "08"],
        ["5", "Skill Enhancement Courses (SEC)", "09", "09"],
        ["6", "Value Added Courses common for all UG", "06 - 08", "06 - 08"],
        ["7", "Summer Internship", "02 - 04", "02 - 04"],
        ["8", "Research Project / Dissertation", "-", "12"],
        ["", "Total", "120", "160"],
    ]
    row_edges = [20, 45, 70, 95, 120, 145, 170]
    for x in continuation_edges:
        page.draw_line((x, row_edges[0]), (x, row_edges[-1]))
    for y in row_edges:
        page.draw_line((continuation_edges[0], y), (continuation_edges[-1], y))
    for row_index, row in enumerate(continuation_rows):
        for column_index, value in enumerate(row):
            if value:
                page.insert_text(
                    (continuation_edges[column_index] + 3, row_edges[row_index] + 18),
                    value,
                    fontsize=7,
                )
    pdf_bytes = pdf.tobytes()
    pdf.close()

    extracted = extract_credit_table_rules(pdf_bytes)
    prose_rules = extract_credit_rules(extract_pdf_pages(pdf_bytes))
    values = {
        (
            rule["category"],
            rule["programme_duration_years"],
            rule["rule_type"],
            rule["value"],
        )
        for rule in extracted
    }
    assert ("Major", 3, "category_min", 60) in values
    assert ("Major", 4, "category_min", 80) in values
    assert ("Minor", 3, "category_min", 24) in values
    assert ("Minor", 4, "category_min", 32) in values
    assert ("Ability Enhancement", 3, "category_min", 8) in values
    assert ("Skill-Based", 4, "category_min", 9) in values
    assert ("Value-Added", 3, "category_min", 6) in values
    assert ("Value-Added", 3, "category_max", 8) in values
    assert ("Value-Added", 4, "category_min", 6) in values
    assert ("Value-Added", 4, "category_max", 8) in values
    assert ("Summer Internship", 3, "category_min", 2) in values
    assert ("Summer Internship", 4, "category_max", 4) in values
    assert ("Research Project", 3, "category_min", None) in values
    assert ("Research Project", 4, "category_min", 12) in values
    assert (None, 3, "total_min", 120) in values
    assert (None, 4, "total_min", 160) in values

    headers = admin_headers(client)
    uploaded = client.post(
        "/api/regulations",
        headers=headers,
        data={
            "title": "UG Credit Requirement Table",
            "issuing_authority": "Academic Board",
            "year": "2026",
            "version": "1.0",
            "programme_level": "ug",
        },
        files={"file": ("credit-table.pdf", pdf_bytes, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["rule_count"] == len(extracted) + len(prose_rules)

    three_year_table = client.get(
        "/api/credit-table",
        headers=headers,
        params={"programme_level": "ug", "duration_years": 3},
    )
    assert three_year_table.status_code == 200
    limits = {
        row["category"]: row
        for row in three_year_table.json()["rows"]
        if row["scope_type"] == "category"
    }
    assert limits["Major"]["minimum"] == "60.00"
    assert limits["Major"]["maximum"] is None
    assert limits["Value-Added"]["minimum"] == "6.00"
    assert limits["Value-Added"]["maximum"] is None
    assert limits["Value-Added"]["credit_value"] == "6–8"
    assert limits["Research Project"]["credit_value"] == "—"
    assert set(limits) == {
        "Major",
        "Minor",
        "Multidisciplinary",
        "Ability Enhancement",
        "Skill-Based",
        "Value-Added",
        "Summer Internship",
        "Research Project",
    }
    assert all(row["total"] is None for row in three_year_table.json()["rows"])
    assert all(
        row["maximum"] is None and row["maximum_source"] is None
        for row in three_year_table.json()["rows"]
        if row["scope_type"] == "category"
    )
    three_year_total = next(row for row in three_year_table.json()["rows"] if row["scope_type"] == "total")
    assert three_year_total["credit_value"] == "120"
    assert three_year_total["minimum"] == "120.00"

    four_year_table = client.get(
        "/api/credit-table",
        headers=headers,
        params={"programme_level": "ug", "duration_years": 4},
    )
    assert four_year_table.status_code == 200
    four_year_limits = {row["category"]: row for row in four_year_table.json()["rows"]}
    assert four_year_limits["Major"]["credit_value"] == "80"
    assert four_year_limits["Minor"]["credit_value"] == "32"
    assert four_year_limits["Research Project"]["credit_value"] == "12"
    four_year_total = next(row for row in four_year_table.json()["rows"] if row["scope_type"] == "total")
    assert four_year_total["credit_value"] == "160"
    assert four_year_total["minimum"] == "160.00"

    updated_pdf = pymupdf.open()
    updated_page = updated_pdf.new_page(width=700, height=220)
    column_edges = [30, 80, 310, 365, 420, 475, 530]
    row_edges = [30, 65, 100, 135, 170]
    for x in column_edges:
        updated_page.draw_line((x, row_edges[0]), (x, row_edges[-1]))
    for y in row_edges:
        updated_page.draw_line((column_edges[0], y), (column_edges[-1], y))
    updated_rows = [
        ["S. No.", "Broad Category of Course", "", "Minimum Credit Requirement", "", ""],
        ["", "", "", "3-year UG", "", "4-year UG"],
        ["1", "Major (Core)", "70", "", "", "90"],
        ["", "Total", "130", "", "", "170"],
    ]
    for row_index, row in enumerate(updated_rows):
        for column_index, text in enumerate(row):
            if text:
                updated_page.insert_text(
                    (column_edges[column_index] + 3, row_edges[row_index] + 24),
                    text,
                    fontsize=8,
                )
    updated_pdf_bytes = updated_pdf.tobytes()
    updated_pdf.close()
    updated_upload = client.post(
        "/api/regulations",
        headers=headers,
        data={
            "title": "UGC curriculum updated",
            "issuing_authority": "University Grants Commission",
            "year": "2026",
            "version": "2.0",
            "programme_level": "ug",
        },
        files={"file": ("ugc-updated.pdf", updated_pdf_bytes, "application/pdf")},
    )
    assert updated_upload.status_code == 201, updated_upload.text
    latest_three_year = client.get(
        "/api/credit-table",
        headers=headers,
        params={"programme_level": "ug", "duration_years": 3},
    ).json()["rows"]
    latest_four_year = client.get(
        "/api/credit-table",
        headers=headers,
        params={"programme_level": "ug", "duration_years": 4},
    ).json()["rows"]
    assert next(row for row in latest_three_year if row["category"] == "Major")["credit_value"] == "70"
    assert next(row for row in latest_four_year if row["category"] == "Major")["credit_value"] == "90"
    assert next(row for row in latest_three_year if row["scope_type"] == "total")["credit_value"] == "130"
    assert next(row for row in latest_four_year if row["scope_type"] == "total")["credit_value"] == "170"

    minimum_override = client.put(
        "/api/credit-table/overrides",
        headers=headers,
        json={
            "programme_level": "ug",
            "scope_type": "category",
            "category": "Major",
            "limit_type": "minimum",
            "value": "65",
        },
    )
    assert minimum_override.status_code == 422, minimum_override.text

    overridden = client.put(
        "/api/credit-table/overrides",
        headers=headers,
        json={
            "programme_level": "ug",
            "scope_type": "category",
            "category": "Major",
            "limit_type": "maximum",
            "value": "85",
        },
    )
    assert overridden.status_code == 200, overridden.text
    major_limit = next(
        row
        for row in client.get(
            "/api/credit-table",
            headers=headers,
            params={"programme_level": "ug", "duration_years": 3},
        ).json()["rows"]
        if row["category"] == "Major"
    )
    assert major_limit["maximum"] == "85.00"
    assert major_limit["maximum_source"]["manual"] is True
    restored = client.delete(
        f"/api/credit-table/overrides/{major_limit['maximum_source']['override_id']}",
        headers=headers,
    )
    major_limit = next(
        row for row in client.get(
            "/api/credit-table",
            headers=headers,
            params={"programme_level": "ug", "duration_years": 3},
        ).json()["rows"]
        if row["category"] == "Major"
    )
    assert major_limit["maximum"] is None
    assert major_limit["maximum_source"] is None


def test_curriculum_library_versions_exports_and_university_scoped_publishing(client, monkeypatch):
    from io import BytesIO

    import pymupdf
    from docx import Document as WordDocument
    from app.schemas import GeneratedCurriculumContent

    headers = admin_headers(client)
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
    }

    async def fake_openai_generation(*, model, programme):
        return GeneratedCurriculumContent.model_validate(generated_payload)

    monkeypatch.setattr("app.config.settings.openai_api_key", "test-api-key")
    monkeypatch.setattr("app.routers.ai_generation.generate_curriculum_with_openai", fake_openai_generation)
    generation = client.post(f"/api/ai-generation/programmes/{programme['id']}", headers=headers)
    assert generation.status_code == 201, generation.text
    generation_job = generation.json()
    assert "regulatory_references" not in generation_job
    assert "validation_status" not in generation_job

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
            "password": "foreign-reviewer-password",
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
    assert "validation_status" not in assignment
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
        json={"email": "foreign-reviewer@example.com", "password": "foreign-reviewer-password"},
    )
    assert foreign_login.status_code == 200
    foreign_headers = {"Authorization": f"Bearer {foreign_login.json()['access_token']}"}
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
