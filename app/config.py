from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Branding
    COMPANY_NAME: str = "Wolfden IT"
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


settings = Settings()
