from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Curriculum Review Platform"
    secret_key: str = "development-only-change-this-secret"
    database_url: str = "sqlite:///./curriculum.db"
    frontend_origin: str = "http://localhost:5173"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = False
    admin_email: str | None = None
    admin_password: str | None = None
    admin_name: str = "Platform Administrator"
    reviewer_email: str | None = None
    reviewer_password: str | None = None
    reviewer_name: str = "University Reviewer"
    reviewer_university_name: str | None = None
    reviewer_university_code: str | None = None
    regulatory_storage_dir: Path = Path("./private_uploads/regulations")
    regulatory_max_upload_bytes: int = 25 * 1024 * 1024
    review_storage_dir: Path = Path("./private_uploads/reviews")
    review_max_upload_bytes: int = 25 * 1024 * 1024
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.app_env.lower() == "production":
            if self.secret_key == "development-only-change-this-secret" or len(self.secret_key) < 32:
                raise ValueError("Production requires a SECRET_KEY with at least 32 characters")
            if not self.cookie_secure:
                raise ValueError("Production requires COOKIE_SECURE=true")
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise ValueError("Production requires a PostgreSQL DATABASE_URL")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
