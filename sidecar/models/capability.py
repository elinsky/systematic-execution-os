"""Capability domain model.

Source of truth: Sidecar.
Deferred to v2 — included in v1 schema as a stub so that capability_id
FK fields in other models don't require a breaking migration later.

The capability_id field is nullable in all v1 models and this module
is not actively used in v1 services.
"""

from enum import StrEnum
from typing import Optional
from pydantic import Field

from .common import SidecarBaseModel


class CapabilityMaturity(StrEnum):
    NONE = "none"
    PLANNED = "planned"
    IN_BUILD = "in_build"
    BASIC = "basic"
    STABLE = "stable"
    MATURE = "mature"


class RoadmapStatus(StrEnum):
    NOT_STARTED = "not_started"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    STABLE = "stable"
    DEPRECATED = "deprecated"


class Capability(SidecarBaseModel):
    """A reusable platform capability that may support multiple PMs.

    V2 artifact — stub included to prevent future schema breaks.

    Examples: security master, real-time market data, DMA connectivity,
    alternative data onboarding, research platform, GPU access.
    """

    capability_id: str
    name: str
    domain: Optional[str] = Field(
        default=None,
        description="e.g. 'market_data', 'execution', 'research', 'infra'",
    )
    owner_team: Optional[str] = None
    current_maturity: CapabilityMaturity = CapabilityMaturity.NONE
    description: Optional[str] = None
    known_gaps: list[str] = Field(default_factory=list)
    dependent_pm_ids: list[str] = Field(default_factory=list)
    linked_project_ids: list[str] = Field(default_factory=list)
    roadmap_status: RoadmapStatus = RoadmapStatus.NOT_STARTED
