"""SQLAlchemy ORM table for Projects.

Source of truth: Asana. Sidecar stores reference + enrichment fields.
"""

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sidecar.db.base import Base, SoftDeleteMixin, TimestampMixin


class ProjectTable(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "project"

    project_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    project_type: Mapped[str] = mapped_column(String, nullable=False)
    business_objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="not_started")
    priority: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    target_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    success_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_status: Mapped[str] = mapped_column(String, nullable=False, default="unknown")
    # Relational IDs stored as JSON arrays
    primary_pm_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    linked_pm_need_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    linked_capability_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Asana sync
    asana_gid: Mapped[str | None] = mapped_column(String, nullable=True, unique=True, index=True)
    asana_synced_at: Mapped[str | None] = mapped_column(String, nullable=True)
