from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.dependencies import CurrentUser
from app.models import College, RefreshSession, University, UniversityStatus, User, UserRole
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    ReviewerSignupOptionsResponse,
    ReviewerSignupRequest,
    ReviewerSignupResponse,
    SignupCollegeOption,
    SignupUniversityOption,
    TokenResponse,
    UserResponse,
)
from app.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
DbSession = Annotated[Session, Depends(get_db)]
REFRESH_COOKIE = "curriculum_refresh"


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/auth",
    )


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role.value,
        university_id=user.university_id,
        university_name=user.university.name if user.university else None,
        college_id=user.college_id,
        college_name=user.college.name if user.college else None,
        must_change_password=user.must_change_password,
    )


def issue_refresh_session(db: Session, user: User) -> str:
    token = create_refresh_token()
    db.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hash_refresh_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
        )
    )
    return token


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: DbSession) -> TokenResponse:
    query = db.query(User).options(joinedload(User.university))
    if payload.email is not None:
        user = query.filter(User.email == str(payload.email).lower()).first()
    else:
        user = query.filter(func.lower(User.username) == payload.username.lower()).first()
    if (
        user is None
        or not user.is_active
        or (payload.expected_role is not None and user.role.value != payload.expected_role.value)
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    refresh_token = issue_refresh_session(db, user)
    db.commit()
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=create_access_token(user.id), user=user_response(user))


@router.get("/signup-options", response_model=ReviewerSignupOptionsResponse)
def reviewer_signup_options(db: DbSession) -> ReviewerSignupOptionsResponse:
    universities = (
        db.query(University)
        .options(joinedload(University.reviewers), joinedload(University.colleges).joinedload(College.reviewers))
        .filter(University.status == UniversityStatus.ACTIVE)
        .order_by(University.name)
        .all()
    )
    options = []
    for university in universities:
        has_university_reviewer = any(
            reviewer.role == UserRole.REVIEWER and reviewer.college_id is None
            for reviewer in university.reviewers
        )
        available_colleges = [
            SignupCollegeOption(id=college.id, name=college.name, code=college.code)
            for college in sorted(university.colleges, key=lambda item: item.name)
            if college.status == "active"
            and not any(reviewer.role == UserRole.REVIEWER for reviewer in college.reviewers)
        ]
        if not has_university_reviewer or available_colleges:
            options.append(
                SignupUniversityOption(
                    id=university.id,
                    name=university.name,
                    code=university.code,
                    university_wide_available=not has_university_reviewer,
                    colleges=available_colleges,
                )
            )
    return ReviewerSignupOptionsResponse(universities=options)


@router.post("/signup", response_model=ReviewerSignupResponse, status_code=status.HTTP_201_CREATED)
def reviewer_signup(payload: ReviewerSignupRequest, db: DbSession) -> ReviewerSignupResponse:
    if db.query(User.id).filter(User.email == str(payload.email).lower()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    college = None
    if payload.university_id is not None:
        university = db.get(University, payload.university_id)
        if university is None or university.status != UniversityStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select an active university")
        if payload.college_id is not None:
            college = db.query(College).filter(
                College.id == payload.college_id,
                College.university_id == university.id,
                College.status == "active",
            ).first()
            if college is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select an active college at this university")
            username = f"{university.code}-{college.code}"[:64]
            if db.query(User.id).filter(User.college_id == college.id, User.role == UserRole.REVIEWER).first():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This college already has a reviewer account")
        else:
            username = university.code
            if db.query(User.id).filter(
                User.university_id == university.id,
                User.role == UserRole.REVIEWER,
                User.college_id.is_(None),
            ).first():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This university already has a reviewer account")
    else:
        university = University(
            name=payload.new_university_name,
            code=payload.new_university_code,
            status=UniversityStatus.INACTIVE,
        )
        db.add(university)
        db.flush()
        username = university.code

    reviewer = User(
        email=str(payload.email).lower(),
        username=username,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.REVIEWER,
        university_id=university.id,
        college_id=college.id if college else None,
        is_active=False,
    )
    db.add(reviewer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email, reviewer ID, university code, or reviewer scope is already registered",
        ) from exc
    return ReviewerSignupResponse(
        message="Signup received. An administrator must approve your account before you can sign in."
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: DbSession) -> TokenResponse:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session required")
    session = (
        db.query(RefreshSession)
        .filter(RefreshSession.token_hash == hash_refresh_token(token))
        .first()
    )
    # Resolve the user separately so the refresh credential can be rotated atomically.
    expires_at = (
        session.expires_at.replace(tzinfo=timezone.utc)
        if session is not None and session.expires_at.tzinfo is None
        else session.expires_at if session is not None else None
    )
    if session is None or expires_at <= datetime.now(timezone.utc):
        if session is not None:
            db.delete(session)
            db.commit()
        response.delete_cookie(REFRESH_COOKIE, path="/api/auth", samesite="lax")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session expired")
    user = db.query(User).options(joinedload(User.university)).filter(User.id == session.user_id).first()
    if user is None or not user.is_active:
        db.delete(session)
        db.commit()
        response.delete_cookie(REFRESH_COOKIE, path="/api/auth", samesite="lax")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is unavailable")
    db.delete(session)
    refresh_token = issue_refresh_session(db, user)
    db.commit()
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=create_access_token(user.id), user=user_response(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> Response:
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        session = db.query(RefreshSession).filter(
            RefreshSession.token_hash == hash_refresh_token(token)
        ).first()
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth", samesite="lax")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return user_response(user)


@router.post("/change-password", response_model=UserResponse)
def change_password(payload: ChangePasswordRequest, user: CurrentUser, db: DbSession) -> UserResponse:
    if len(payload.new_password) < 12:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 12 characters")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.query(RefreshSession).filter(RefreshSession.user_id == user.id).delete()
    db.commit()
    return user_response(user)
