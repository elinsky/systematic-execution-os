"""PM Coverage Record domain model.

Source of truth: Sidecar.
Asana representation: One summary task in the PM Coverage tracking project.
"""

from datetime import date
from enum import StrEnum

from pydantic import Field

from .common import AsanaLinkedRecord, HealthStatus


class OnboardingStage(StrEnum):
    PIPELINE = "pipeline"
    PRE_START = "pre_start"
    REQUIREMENTS_DISCOVERY = "requirements_discovery"
    ONBOARDING_IN_PROGRESS = "onboarding_in_progress"
    UAT = "uat"
    GO_LIVE_READY = "go_live_ready"
    LIVE = "live"
    STABILIZATION = "stabilization"
    STEADY_STATE = "steady_state"


class PMCoverageRecord(AsanaLinkedRecord):
    """A persistent record for each PM or team being supported.

    This is a first-class sidecar object because PM-specific needs, milestones,
    and health signals cannot be modeled richly in Asana natively.
    """

    pm_id: str = Field(description="Internal sidecar identifier, e.g. 'pm-jane-doe'")
    pm_name: str
    team_or_pod: str | None = None
    strategy_type: str | None = Field(
        default=None,
        description="e.g. 'US Equities Long/Short', 'Global Macro'",
    )
    region: str | None = None
    coverage_owner: str | None = Field(
        default=None,
        description="BAM Systematic staff member responsible for this PM relationship",
    )
    onboarding_stage: OnboardingStage = OnboardingStage.PIPELINE
    go_live_target_date: date | None = None
    health_status: HealthStatus = HealthStatus.UNKNOWN
    last_touchpoint_date: date | None = None
    notes: str | None = None

    # Relational links (stored as ID lists; resolved at query time)
    linked_project_ids: list[str] = Field(default_factory=list)
    # NOTE: top_open_need_ids and top_blocker_ids are computed on read
    # from PMNeed and RiskBlocker tables filtered by pm_id, not stored here.
    # See design-review.md P1 item #5.


class PMCoverageCreate(PMCoverageRecord):
    """Schema for creating a new PM Coverage Record."""

    # pm_id must be provided by caller on creation
    pm_id: str
    pm_name: str


class PMCoverageUpdate(AsanaLinkedRecord):
    """Schema for partial updates to a PM Coverage Record."""

    pm_id: str
    onboarding_stage: OnboardingStage | None = None
    health_status: HealthStatus | None = None
    go_live_target_date: date | None = None
    coverage_owner: str | None = None
    last_touchpoint_date: date | None = None
    notes: str | None = None
