from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal, engine
from app.models import University, UniversityStatus, User, UserRole
from app.routers import ai_generation, auth, colleges, courses, curricula, curriculum_structures, dashboard, programmes, regulations, reviews, reviewers, universities
from app.schemas import HealthResponse
from app.security import hash_password


def seed_initial_accounts() -> None:
    with SessionLocal() as db:
        if settings.admin_email and settings.admin_password:
            admin_email = settings.admin_email.lower()
            admin = db.query(User).filter(User.email == admin_email).first()
            if admin is None:
                db.add(
                    User(
                        id=uuid4(),
                        email=admin_email,
                        full_name=settings.admin_name,
                        password_hash=hash_password(settings.admin_password),
                        role=UserRole.ADMIN,
                    )
                )
        if settings.reviewer_email and settings.reviewer_password:
            reviewer_email = settings.reviewer_email.lower()
            reviewer = db.query(User).filter(User.email == reviewer_email).first()
            if reviewer is None:
                if not settings.reviewer_university_name or not settings.reviewer_university_code:
                    raise ValueError("Reviewer bootstrap requires REVIEWER_UNIVERSITY_NAME and REVIEWER_UNIVERSITY_CODE")
                university = db.query(University).filter(
                    University.code == settings.reviewer_university_code.upper()
                ).first()
                if university is None:
                    university = University(
                        name=settings.reviewer_university_name,
                        code=settings.reviewer_university_code.upper(),
                        status=UniversityStatus.ACTIVE,
                    )
                    db.add(university)
                    db.flush()
                db.add(
                    User(
                        email=reviewer_email,
                        full_name=settings.reviewer_name,
                        password_hash=hash_password(settings.reviewer_password),
                        role=UserRole.REVIEWER,
                        username=university.code,
                        university_id=university.id,
                        must_change_password=True,
                    )
                )
        db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    seed_initial_accounts()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(universities.router)
app.include_router(colleges.router)
app.include_router(courses.router)
app.include_router(curriculum_structures.router)
app.include_router(reviewers.router)
app.include_router(regulations.router)
app.include_router(regulations.rules_router)
app.include_router(programmes.router)
app.include_router(ai_generation.router)
app.include_router(curricula.router)
app.include_router(reviews.router)


@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database connection unavailable") from exc
    return HealthResponse(status="ok", database="connected")
