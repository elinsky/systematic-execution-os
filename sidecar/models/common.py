"""Shared enums, base classes, and types used across all domain models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------


class SidecarBaseModel(BaseModel):
    """Root Pydantic base for all sidecar domain models.

    - Extra fields are forbidden to catch schema drift early.
    - Use `model_config` to enable from_attributes for ORM compatibility.
    """

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
    )


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class HealthStatus(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Urgency(StrEnum):
    IMMEDIATE = "immediate"
    THIS_WEEK = "this_week"
    THIS_MONTH = "this_month"
    NEXT_QUARTER = "next_quarter"
    BACKLOG = "backlog"


class BusinessImpact(StrEnum):
    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Shared base for records with Asana GID
# ---------------------------------------------------------------------------


class AsanaLinkedRecord(SidecarBaseModel):
    """Base for sidecar records that mirror an Asana object.

    V1 uses asana_gid + asana_synced_at for sync tracking.
    Full SyncState machine (pending_push/pull/conflict) deferred to v2.
    See design-review.md P3 recommendation.
    """

    asana_gid: str | None = Field(
        default=None,
        description="Asana global ID for the mirrored object. "
        "Non-nullable once synced; None only before first Asana write.",
    )
    asana_synced_at: datetime | None = Field(
        default=None,
        description="Timestamp of last successful sync with Asana.",
    )
    created_at: datetime | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None
