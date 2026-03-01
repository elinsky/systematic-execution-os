"""PM Coverage Record domain model.

Source of truth: Sidecar.
Asana representation: One summary task in the PM Coverage tracking project.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Optional
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
    team_or_pod: Optional[str] = None
    strategy_type: Optional[str] = Field(
        default=None,
        description="e.g. 'US Equities Long/Short', 'Global Macro'",
    )
    region: Optional[str] = None
    coverage_owner: Optional[str] = Field(
        default=None,
        description="BAM Systematic staff member responsible for this PM relationship",
    )
    onboarding_stage: OnboardingStage = OnboardingStage.PIPELINE
    go_live_target_date: Optional[date] = None
    health_status: HealthStatus = HealthStatus.UNKNOWN
    last_touchpoint_date: Optional[date] = None
    notes: Optional[str] = None

    # Relational links (stored as ID lists; resolved at query time)
    linked_project_ids: list[str] = Field(default_factory=list)
    top_open_need_ids: list[str] = Field(default_factory=list)
    top_blocker_ids: list[str] = Field(default_factory=list)


class PMCoverageCreate(PMCoverageRecord):
    """Schema for creating a new PM Coverage Record."""

    # pm_id must be provided by caller on creation
    pm_id: str
    pm_name: str


class PMCoverageUpdate(AsanaLinkedRecord):
    """Schema for partial updates to a PM Coverage Record."""

    pm_id: str
    onboarding_stage: Optional[OnboardingStage] = None
    health_status: Optional[HealthStatus] = None
    go_live_target_date: Optional[date] = None
    coverage_owner: Optional[str] = None
    last_touchpoint_date: Optional[date] = None
    notes: Optional[str] = None
