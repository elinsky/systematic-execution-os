"""Deliverable / Action Item domain model.

Source of truth: Asana.
Sidecar tracks asana_gid reference only; does not replicate task body or comments.
"""

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from .common import AsanaLinkedRecord


class DeliverableStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class Deliverable(AsanaLinkedRecord):
    """A concrete owned work item — the lowest-level tracked unit.

    Maps to an Asana task or subtask. The sidecar stores the GID and key
    metadata for rollup queries (overdue detection, weekly review prep).
    """

    deliverable_id: str = Field(description="Internal sidecar identifier")
    project_id: str = Field(description="FK to Project.project_id")
    title: str
    owner: str | None = None
    due_date: date | None = None
    status: DeliverableStatus = DeliverableStatus.NOT_STARTED
    related_milestone_id: str | None = Field(
        default=None,
        description="FK to Milestone.milestone_id if this deliverable gates a milestone",
    )
    blocked_by: list[str] = Field(
        default_factory=list,
        description="List of deliverable_ids this item is waiting on",
    )
    last_updated: datetime | None = None
    notes: str | None = None


class DeliverableCreate(Deliverable):
    deliverable_id: str
    project_id: str
    title: str


class DeliverableUpdate(AsanaLinkedRecord):
    deliverable_id: str
    status: DeliverableStatus | None = None
    owner: str | None = None
    due_date: date | None = None
    notes: str | None = None
