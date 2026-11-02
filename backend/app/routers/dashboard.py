from fastapi import APIRouter, Depends
from sqlalchemy import func

from app.dependencies import DbSession, require_role
from app.models import CurriculumAssignment, CurriculumGenerationJob, Programme, University, User, UserRole
from app.schemas import AdminDashboardResponse, ReviewerDashboardResponse

router = APIRouter(prefix="/api", tags=["dashboards"])


@router.get("/admin/dashboard", response_model=AdminDashboardResponse)
def admin_dashboard(
    db: DbSession,
    _admin: User = Depends(require_role(UserRole.ADMIN)),
) -> AdminDashboardResponse:
    return AdminDashboardResponse(
        total_universities=db.query(func.count(University.id)).scalar() or 0,
        reviewer_accounts=db.query(func.count(User.id)).filter(User.role == UserRole.REVIEWER).scalar() or 0,
        total_programmes=db.query(func.count(Programme.id)).scalar() or 0,
        total_curricula=db.query(func.count(CurriculumGenerationJob.id))
        .filter(CurriculumGenerationJob.status == "completed")
        .scalar()
        or 0,
    )


@router.get("/reviewer/dashboard", response_model=ReviewerDashboardResponse)
def reviewer_dashboard(
    db: DbSession,
    reviewer: User = Depends(require_role(UserRole.REVIEWER)),
) -> ReviewerDashboardResponse:
    assignments = db.query(CurriculumAssignment).filter(CurriculumAssignment.reviewer_id == reviewer.id)
    return ReviewerDashboardResponse(
        university_name=reviewer.university.name if reviewer.university else "University not assigned",
        assigned_curricula=assignments.count(),
        pending_reviews=assignments.filter(CurriculumAssignment.status == "pending").count(),
        under_review=assignments.filter(CurriculumAssignment.status == "under_review").count(),
        revision_requested=assignments.filter(CurriculumAssignment.status == "revision_requested").count(),
        approved_curricula=assignments.filter(CurriculumAssignment.status == "approved").count(),
    )
