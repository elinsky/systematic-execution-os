"""SQLAlchemy ORM table for Capabilities.

Source of truth: Sidecar. V2 feature — stub included so capability_id FK
fields in v1 tables don't require a future breaking migration.
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sidecar.db.base import Base, TimestampMixin


class CapabilityTable(Base, TimestampMixin):
    __tablename__ = "capability"

    capability_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_team: Mapped[str | None] = mapped_column(String, nullable=True)
    current_maturity: Mapped[str] = mapped_column(String, nullable=False, default="not_started")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    roadmap_status: Mapped[str] = mapped_column(String, nullable=False, default="not_planned")
    # Relational IDs stored as JSON arrays
    known_gaps: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    dependent_pm_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    linked_project_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Asana sync (optional — capability may or may not have an Asana project)
    asana_gid: Mapped[str | None] = mapped_column(String, nullable=True, unique=True, index=True)
    asana_synced_at: Mapped[str | None] = mapped_column(String, nullable=True)
