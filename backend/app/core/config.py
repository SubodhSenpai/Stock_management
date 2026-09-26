"""Application settings, read from environment variables (and backend/.env in development)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "StockSense API"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    database_url: str
    test_database_url: str | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 10
    sql_echo: bool = False

    jwt_secret: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=720, gt=0)
    auth_cookie_name: str = "access_token"
    cookie_secure: bool = False

    otp_secret: str = Field(min_length=16)
    otp_expire_minutes: int = Field(default=10, gt=0)
    otp_max_attempts: int = Field(default=5, gt=0)
    otp_resend_cooldown_seconds: int = Field(default=60, ge=0)

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str = "StockSense <no-reply@stocksense.local>"

    frontend_origin: str = "http://localhost:3000"

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached so .env is parsed once)."""
    return Settings()
