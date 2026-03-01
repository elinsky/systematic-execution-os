"""PM Need domain model.

Source of truth: Hybrid.
- Asana: intake task in the PM Needs project (operational store).
- Sidecar: relational metadata, status enrichment, links to capabilities/projects.
"""

from datetime import date
from enum import StrEnum

from pydantic import Field

from .common import AsanaLinkedRecord, BusinessImpact, Urgency


class NeedCategory(StrEnum):
    MARKET_DATA = "market_data"
    HISTORICAL_DATA = "historical_data"
    ALT_DATA = "alt_data"
    EXECUTION = "execution"
    BROKER = "broker"
    INFRA = "infra"
    RESEARCH = "research"
    OPS = "ops"
    OTHER = "other"


class NeedStatus(StrEnum):
    NEW = "new"
    TRIAGED = "triaged"
    MAPPED_TO_EXISTING_CAPABILITY = "mapped_to_existing_capability"
    NEEDS_NEW_PROJECT = "needs_new_project"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DELIVERED = "delivered"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class PMNeed(AsanaLinkedRecord):
    """A normalized business request or ask from a PM or systematic leadership.

    One of the most important objects in the system: everything routes through
    PM needs to ensure visibility and prioritization.
    """

    pm_need_id: str = Field(description="Internal sidecar identifier")
    pm_id: str = Field(description="FK to PMCoverageRecord.pm_id")
    title: str = Field(
        description="Short, clear statement of the need. "
        "Should follow naming convention: '[PM] - [Category] - [Short Need]'",
    )
    problem_statement: str | None = None
    business_rationale: str | None = None
    requested_by: str = Field(description="Name of PM or leadership contact who raised this")
    date_raised: date
    category: NeedCategory
    urgency: Urgency = Urgency.THIS_MONTH
    business_impact: BusinessImpact = BusinessImpact.MEDIUM
    desired_by_date: date | None = None
    status: NeedStatus = NeedStatus.NEW

    # Routing / resolution
    mapped_capability_id: str | None = Field(
        default=None,
        description="FK to Capability.capability_id if this need maps to an existing capability",
    )
    linked_project_ids: list[str] = Field(default_factory=list)
    resolution_path: str | None = Field(
        default=None,
        description="Free-text description of how this need will be or was resolved",
    )
    notes: str | None = None


class PMNeedCreate(PMNeed):
    """Schema for creating a new PM Need (creates Asana task + sidecar record)."""

    pm_need_id: str
    pm_id: str
    title: str
    requested_by: str
    date_raised: date
    category: NeedCategory


class PMNeedUpdate(AsanaLinkedRecord):
    """Schema for partial updates to a PM Need.

    NOTE: `status` is NOT writable via the sidecar API. PM Need status is
    driven by the Asana task's section (Kanban column). The sidecar's `status`
    field is a read-only cache synced from Asana via webhook/poll.
    See design-review.md P0 item #1.
    """

    pm_need_id: str
    # status intentionally excluded — Asana section is canonical
    urgency: Urgency | None = None
    business_impact: BusinessImpact | None = None
    mapped_capability_id: str | None = None
    linked_project_ids: list[str] | None = None
    resolution_path: str | None = None
    notes: str | None = None
