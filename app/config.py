from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR = Path("/app/data")
LOGO_EXTS = ("png", "jpg", "jpeg", "svg", "gif")


def find_logo_path() -> Path | None:
    for ext in LOGO_EXTS:
        p = DATA_DIR / f"logo.{ext}"
        if p.exists():
            return p
    return None


def normalize_url(v: str) -> str:
    """Accept "192.168.1.50:11434" as well as "http://192.168.1.50:11434/"."""
    v = v.strip().rstrip("/")
    if v and "://" not in v:
        v = "http://" + v
    return v


class Settings(BaseSettings):
    # Branding
    COMPANY_NAME: str = "SwyfTech"
    COMPANY_TAGLINE: str = "Managed IT Services"
    COMPANY_EMAIL: str = ""
    COMPANY_PHONE: str = ""
    COMPANY_WEBSITE: str = ""

    # LLM
    LLM_PROVIDER: str = "ollama"  # "anthropic" or "ollama"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = ""
    SMTP_TLS: bool = True

    # DB
    DATABASE_URL: str = "sqlite:////app/data/msp.db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("LLM_PROVIDER")
    @classmethod
    def _normalize_provider(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("OLLAMA_BASE_URL")
    @classmethod
    def _normalize_ollama_url(cls, v: str) -> str:
        return normalize_url(v)


settings = Settings()
