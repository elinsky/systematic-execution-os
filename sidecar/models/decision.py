"""Decision domain model.

Source of truth: Sidecar (sidecar-only, no Asana representation required).

Decisions are append-only: they should never be deleted, only superseded.
This preserves rationale and prevents repeated re-litigation of resolved choices.
"""

from datetime import date
from enum import StrEnum
from typing import Optional
from pydantic import Field

from .common import SidecarBaseModel


class DecisionStatus(StrEnum):
    PENDING = "pending"
    DECIDED = "decided"
    SUPERSEDED = "superseded"
    DEFERRED = "deferred"


class ArtifactType(StrEnum):
    """Types of artifacts that a decision can impact."""
    PM = "pm"
    PROJECT = "project"
    MILESTONE = "milestone"
    PM_NEED = "pm_need"
    CAPABILITY = "capability"
    RISK = "risk"


class ImpactedArtifact(SidecarBaseModel):
    artifact_type: ArtifactType
    artifact_id: str
    description: Optional[str] = None


class Decision(SidecarBaseModel):
    """A durable record of a meaningful business or technology tradeoff.

    Examples:
    - Choose broker A over broker B
    - Reuse existing capability instead of custom build
    - Phase work into v1/v2
    - Defer non-critical feature to hit go-live

    Append-only design: set status to SUPERSEDED and link to the new decision
    rather than modifying or deleting.
    """

    decision_id: str = Field(description="Internal sidecar identifier")
    title: str
    context: Optional[str] = Field(
        default=None,
        description="Background and situation that required this decision",
    )
    options_considered: Optional[str] = Field(
        default=None,
        description="Description of alternatives evaluated",
    )
    chosen_path: Optional[str] = Field(
        default=None,
        description="The selected option",
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Why this option was chosen over alternatives",
    )
    approvers: list[str] = Field(
        default_factory=list,
        description="Names/IDs of decision approvers",
    )
    decision_date: Optional[date] = None
    status: DecisionStatus = DecisionStatus.PENDING
    superseded_by_id: Optional[str] = Field(
        default=None,
        description="decision_id of the decision that supersedes this one",
    )
    impacted_artifacts: list[ImpactedArtifact] = Field(default_factory=list)
    created_at: Optional[date] = None
    notes: Optional[str] = None


class DecisionCreate(Decision):
    decision_id: str
    title: str


class DecisionResolve(SidecarBaseModel):
    """Schema for recording the outcome of a pending decision."""
    decision_id: str
    chosen_path: str
    rationale: str
    approvers: list[str]
    decision_date: date
