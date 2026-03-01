"""Shared enums, base classes, and types used across all domain models."""

from datetime import datetime
from enum import StrEnum
from typing import Optional
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


class SyncState(StrEnum):
    """Tracks the sidecar record's synchronization state with Asana."""
    SYNCED = "synced"
    PENDING_PUSH = "pending_push"
    PENDING_PULL = "pending_pull"
    CONFLICT = "conflict"
    ASANA_DELETED = "asana_deleted"


# ---------------------------------------------------------------------------
# Shared base for records with Asana GID
# ---------------------------------------------------------------------------

class AsanaLinkedRecord(SidecarBaseModel):
    """Base for sidecar records that mirror an Asana object."""

    asana_gid: Optional[str] = Field(
        default=None,
        description="Asana global ID for the mirrored object. "
                    "Non-nullable once synced; None only before first Asana write.",
    )
    sync_state: SyncState = SyncState.PENDING_PUSH
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
