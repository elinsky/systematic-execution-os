"""Application configuration via Pydantic BaseSettings.

All settings are loaded from environment variables or a .env file.
See .env.example for required variables.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Asana credentials ──────────────────────────────────────────────────────
    asana_personal_access_token: str = Field(description="Asana personal access token")
    asana_workspace_gid: str = Field(description="Asana workspace GID")

    # ── Asana project GIDs ─────────────────────────────────────────────────────
    asana_pm_needs_project_gid: str = ""
    asana_pm_coverage_project_gid: str = ""
    asana_risks_project_gid: str = ""

    # ── Asana custom field GIDs ────────────────────────────────────────────────
    asana_custom_field_pm_id: str = ""
    asana_custom_field_urgency: str = ""
    asana_custom_field_health: str = ""
    asana_custom_field_priority: str = ""
    asana_custom_field_business_impact: str = ""

    # ── Asana webhook ──────────────────────────────────────────────────────────
    asana_webhook_secret: str = ""

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./bam_execution.db"

    # ── API server ─────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Scheduler cron expressions ─────────────────────────────────────────────
    daily_digest_cron: str = "0 7 * * *"
    weekly_review_cron: str = "0 8 * * MON"

    # ── Alert thresholds ───────────────────────────────────────────────────────
    blocker_age_alert_days: int = 7
    milestone_due_alert_days: int = 7
    pm_open_needs_alert_count: int = 3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached Settings instance. Used as a FastAPI dependency."""
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
