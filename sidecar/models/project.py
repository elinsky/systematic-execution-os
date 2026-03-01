"""Project domain model.

Source of truth: Asana.
Sidecar stores asana_gid reference and enrichment fields only.
"""

from datetime import date
from enum import StrEnum

from pydantic import Field

from .common import AsanaLinkedRecord, HealthStatus, Priority


class ProjectType(StrEnum):
    PM_ONBOARDING = "pm_onboarding"
    CAPABILITY_BUILD = "capability_build"
    REMEDIATION = "remediation"
    EXPANSION = "expansion"
    INVESTIGATION = "investigation"


class ProjectStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    AT_RISK = "at_risk"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class Project(AsanaLinkedRecord):
    """A bounded execution effort that delivers a business outcome.

    Maps 1:1 to an Asana project in most cases. The sidecar stores the
    asana_gid and enrichment fields (linked PM needs, capabilities, health).

    Naming convention: '[Type] - [PM or Capability] - [Short Outcome]'
    Example: 'Onboarding - PM Jane Doe - US Equities Launch'
    """

    project_id: str = Field(description="Internal sidecar identifier")
    name: str
    project_type: ProjectType
    business_objective: str | None = None
    success_criteria: str | None = None
    primary_pm_ids: list[str] = Field(
        default_factory=list,
        description="FKs to PMCoverageRecord.pm_id",
    )
    owner: str | None = None
    status: ProjectStatus = ProjectStatus.PLANNING
    priority: Priority = Priority.MEDIUM
    health: HealthStatus = HealthStatus.UNKNOWN
    start_date: date | None = None
    target_date: date | None = None

    # Relational links (stored as ID lists; resolved at query time)
    linked_pm_need_ids: list[str] = Field(default_factory=list)
    linked_capability_ids: list[str] = Field(default_factory=list)  # v2 capability FK
    linked_milestone_ids: list[str] = Field(default_factory=list)
    linked_risk_ids: list[str] = Field(default_factory=list)
    linked_decision_ids: list[str] = Field(default_factory=list)


class ProjectCreate(Project):
    project_id: str
    name: str
    project_type: ProjectType


class ProjectUpdate(AsanaLinkedRecord):
    project_id: str
    status: ProjectStatus | None = None
    health: HealthStatus | None = None
    priority: Priority | None = None
    owner: str | None = None
    target_date: date | None = None
    success_criteria: str | None = None
