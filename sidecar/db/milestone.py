"""SQLAlchemy ORM table for Milestones.

Source of truth: Asana. Sidecar stores reference + enrichment fields.
"""

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sidecar.db.base import Base, TimestampMixin


class MilestoneTable(Base, TimestampMixin):
    __tablename__ = "milestone"

    milestone_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("project.project_id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    target_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    owner: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="not_started")
    confidence: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    gating_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Asana sync
    asana_gid: Mapped[str | None] = mapped_column(String, nullable=True, unique=True, index=True)
    asana_synced_at: Mapped[str | None] = mapped_column(String, nullable=True)
