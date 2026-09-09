"""Application settings loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Loaded from environment variables with sensible defaults where applicable.
    Also reads from a ``.env`` file in the backend directory if present.
    """

    database_path: str = "data/db.json"
    jwt_secret: str  # required — no default
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 30
    jwt_reset_token_expiry_minutes: int = Field(default=15, ge=15, le=60)
    cors_origins: list[str] = ["http://localhost:3000"]
    frontend_base_url: str = "http://localhost:3000"
    resend_api_key: str | None = None
    resend_from_email: str = "onboarding@resend.dev"

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        env_file=".env",
        extra="ignore",
    )


settings = Settings()