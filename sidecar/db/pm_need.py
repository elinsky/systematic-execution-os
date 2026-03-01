"""SQLAlchemy ORM table for PM Needs.

Source of truth: Hybrid (Asana task + sidecar metadata).
"""

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sidecar.db.base import Base, SoftDeleteMixin, TimestampMixin


class PMNeedTable(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "pm_need"

    need_id: Mapped[str] = mapped_column(String, primary_key=True)
    pm_id: Mapped[str] = mapped_column(
        String, ForeignKey("pm_coverage.pm_id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    problem_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str] = mapped_column(String, nullable=False)
    date_raised: Mapped[str] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    urgency: Mapped[str] = mapped_column(String, nullable=False)
    business_impact: Mapped[str | None] = mapped_column(String, nullable=True)
    desired_by_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="new")
    resolution_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Relational IDs
    linked_project_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    mapped_capability_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Asana sync
    asana_gid: Mapped[str | None] = mapped_column(String, nullable=True, unique=True, index=True)
    asana_synced_at: Mapped[str | None] = mapped_column(String, nullable=True)
