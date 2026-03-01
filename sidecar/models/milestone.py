"""Milestone domain model.

Source of truth: Asana.
Sidecar stores asana_gid + computed confidence and acceptance criteria enrichment.
"""

from datetime import date
from enum import StrEnum

from pydantic import Field

from .common import AsanaLinkedRecord


class MilestoneStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    AT_RISK = "at_risk"
    COMPLETE = "complete"
    MISSED = "missed"
    DEFERRED = "deferred"


class MilestoneConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


# Standard milestone names used in PM onboarding template
STANDARD_ONBOARDING_MILESTONES = [
    "Kickoff",
    "Requirements Confirmed",
    "Market Data Ready",
    "Historical Data Ready",
    "Alt Data Ready",
    "Execution Ready",
    "UAT Complete",
    "Go-Live Ready",
    "PM Live",
    "Stabilization Complete",
]


class Milestone(AsanaLinkedRecord):
    """A named checkpoint with explicit gating criteria.

    Maps to an Asana milestone task inside a project.

    Naming convention: '[Project/PM] - [Checkpoint]'
    Example: 'PM Jane Doe - Go Live Ready'
    """

    milestone_id: str = Field(description="Internal sidecar identifier")
    project_id: str = Field(description="FK to Project.project_id")
    name: str
    target_date: date | None = None
    owner: str | None = None
    status: MilestoneStatus = MilestoneStatus.NOT_STARTED
    confidence: MilestoneConfidence = MilestoneConfidence.UNKNOWN
    gating_conditions: str | None = Field(
        default=None,
        description="What must be true for this milestone to be considered reachable",
    )
    acceptance_criteria: str | None = Field(
        default=None,
        description="What must be true for this milestone to be marked complete",
    )
    notes: str | None = None


class MilestoneCreate(Milestone):
    milestone_id: str
    project_id: str
    name: str


class MilestoneUpdate(AsanaLinkedRecord):
    milestone_id: str
    status: MilestoneStatus | None = None
    confidence: MilestoneConfidence | None = None
    target_date: date | None = None
    owner: str | None = None
    acceptance_criteria: str | None = None
    notes: str | None = None
