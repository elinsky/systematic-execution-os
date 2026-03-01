"""SQLAlchemy ORM table for Decisions.

Source of truth: Sidecar. Append-only — decisions are never deleted.
"""

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sidecar.db.base import Base, TimestampMixin


class DecisionTable(Base, TimestampMixin):
    __tablename__ = "decision"

    decision_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    options_considered: Mapped[str | None] = mapped_column(Text, nullable=True)
    chosen_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    approvers: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    decision_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    # Relational IDs stored as JSON arrays
    impacted_artifact_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Decisions are sidecar-only; no Asana GID required
