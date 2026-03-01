"""SQLAlchemy ORM table for Risks / Blockers / Issues.

Source of truth: Hybrid (Asana task + sidecar severity/impact metadata).
"""

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sidecar.db.base import Base, TimestampMixin


class RiskTable(Base, TimestampMixin):
    __tablename__ = "risk"

    risk_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    risk_type: Mapped[str] = mapped_column(String, nullable=False, default="risk")
    severity: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    owner: Mapped[str | None] = mapped_column(String, nullable=True)
    date_opened: Mapped[str] = mapped_column(Date, nullable=False)
    resolution_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    mitigation_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_status: Mapped[str] = mapped_column(String, nullable=False, default="not_escalated")
    # Relational IDs stored as JSON arrays
    impacted_pm_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    impacted_project_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    impacted_milestone_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Asana sync
    asana_gid: Mapped[str | None] = mapped_column(String, nullable=True, unique=True, index=True)
    asana_synced_at: Mapped[str | None] = mapped_column(String, nullable=True)
