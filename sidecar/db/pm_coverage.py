"""SQLAlchemy ORM table for PM Coverage Records.

Source of truth: Sidecar.
"""

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sidecar.db.base import Base, SoftDeleteMixin, TimestampMixin


class PMCoverageTable(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "pm_coverage"

    pm_id: Mapped[str] = mapped_column(String, primary_key=True)
    pm_name: Mapped[str] = mapped_column(String, nullable=False)
    team_or_pod: Mapped[str | None] = mapped_column(String, nullable=True)
    strategy_type: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    coverage_owner: Mapped[str | None] = mapped_column(String, nullable=True)
    onboarding_stage: Mapped[str] = mapped_column(String, nullable=False, default="pipeline")
    go_live_target_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    health_status: Mapped[str] = mapped_column(String, nullable=False, default="unknown")
    last_touchpoint_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Relational IDs stored as JSON arrays in TEXT columns (SQLite-friendly)
    linked_project_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Asana sync fields
    asana_gid: Mapped[str | None] = mapped_column(String, nullable=True, unique=True, index=True)
    asana_synced_at: Mapped[str | None] = mapped_column(String, nullable=True)
