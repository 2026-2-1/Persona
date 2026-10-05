from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://persona:persona_dev@127.0.0.1:15432/persona"
    redis_url: str = "redis://127.0.0.1:16379/0"
    artifact_dir: Path = PROJECT_ROOT / "artifacts"
    fixture_base_url: str = "http://127.0.0.1:8000/fixtures/shop"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    model_provider: Literal["mock"] = "mock"

    @field_validator("fixture_base_url")
    @classmethod
    def fixed_fixture_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path != "/fixtures/shop"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("FIXTURE_BASE_URL must be an HTTP(S) URL ending in /fixtures/shop")
        _ = parsed.port  # Validate malformed ports before the worker starts.
        return value.rstrip("/")

    @field_validator("artifact_dir")
    @classmethod
    def resolve_artifacts(cls, value: Path) -> Path:
        return (PROJECT_ROOT / value).resolve() if not value.is_absolute() else value.resolve()

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
