"""Settings editable from the UI, layered over the env-driven defaults in config.py.

Secrets (ANTHROPIC_API_KEY, SMTP_PASS) are deliberately not editable here — they
only ever come from environment variables."""

import json
from typing import Dict

from .config import Settings, settings
from .database import SessionLocal
from .models import AppSetting

EDITABLE_KEYS = (
    "COMPANY_NAME",
    "COMPANY_TAGLINE",
    "COMPANY_EMAIL",
    "COMPANY_PHONE",
    "COMPANY_WEBSITE",
    "LLM_PROVIDER",
    "ANTHROPIC_MODEL",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_FROM",
    "SMTP_TLS",
)


def env_defaults() -> Dict:
    """The values the app would use with no in-app overrides."""
    return {k: getattr(settings, k) for k in EDITABLE_KEYS}


def load_overrides() -> Dict:
    db = SessionLocal()
    try:
        rows = db.query(AppSetting).filter(AppSetting.key.in_(EDITABLE_KEYS)).all()
        return {r.key: json.loads(r.value) for r in rows}
    finally:
        db.close()


def get_settings() -> Settings:
    """Effective settings: env defaults with any in-app overrides applied."""
    overrides = load_overrides()
    if not overrides:
        return settings
    return settings.model_copy(update=overrides)


def save_settings(values: Dict) -> None:
    """Persist values that differ from the env defaults; drop overrides that now match,
    so later env changes still take effect for those keys."""
    defaults = env_defaults()
    db = SessionLocal()
    try:
        for key, value in values.items():
            if key not in EDITABLE_KEYS:
                continue
            row = db.get(AppSetting, key)
            if value == defaults[key]:
                if row:
                    db.delete(row)
            elif row:
                row.value = json.dumps(value)
            else:
                db.add(AppSetting(key=key, value=json.dumps(value)))
        db.commit()
    finally:
        db.close()


def reset_settings() -> None:
    db = SessionLocal()
    try:
        db.query(AppSetting).delete()
        db.commit()
    finally:
        db.close()
