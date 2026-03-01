"""Sidecar domain models.

All Pydantic v2 domain models for the BAM Systematic Execution OS sidecar.
"""

from .capability import (
    Capability,
    CapabilityMaturity,
    RoadmapStatus,
)
from .common import (
    AsanaLinkedRecord,
    BusinessImpact,
    HealthStatus,
    Priority,
    SidecarBaseModel,
    Urgency,
)
from .decision import (
    ArtifactType,
    Decision,
    DecisionCreate,
    DecisionResolve,
    DecisionStatus,
    ImpactedArtifact,
)
from .deliverable import (
    Deliverable,
    DeliverableCreate,
    DeliverableStatus,
    DeliverableUpdate,
)
from .milestone import (
    STANDARD_ONBOARDING_MILESTONES,
    Milestone,
    MilestoneConfidence,
    MilestoneCreate,
    MilestoneStatus,
    MilestoneUpdate,
)
from .pm_coverage import (
    OnboardingStage,
    PMCoverageCreate,
    PMCoverageRecord,
    PMCoverageUpdate,
)
from .pm_need import (
    NeedCategory,
    NeedStatus,
    PMNeed,
    PMNeedCreate,
    PMNeedUpdate,
)
from .project import (
    Project,
    ProjectCreate,
    ProjectStatus,
    ProjectType,
    ProjectUpdate,
)
from .risk import (
    EscalationStatus,
    RiskBlocker,
    RiskCreate,
    RiskSeverity,
    RiskStatus,
    RiskType,
    RiskUpdate,
)
from .status_update import (
    StatusScopeType,
    StatusUpdate,
)

__all__ = [
    # common
    "SidecarBaseModel",
    "AsanaLinkedRecord",
    "HealthStatus",
    "Priority",
    "Urgency",
    "BusinessImpact",
    # pm_coverage
    "OnboardingStage",
    "PMCoverageRecord",
    "PMCoverageCreate",
    "PMCoverageUpdate",
    # pm_need
    "NeedCategory",
    "NeedStatus",
    "PMNeed",
    "PMNeedCreate",
    "PMNeedUpdate",
    # project
    "ProjectType",
    "ProjectStatus",
    "Project",
    "ProjectCreate",
    "ProjectUpdate",
    # milestone
    "MilestoneStatus",
    "MilestoneConfidence",
    "STANDARD_ONBOARDING_MILESTONES",
    "Milestone",
    "MilestoneCreate",
    "MilestoneUpdate",
    # deliverable
    "DeliverableStatus",
    "Deliverable",
    "DeliverableCreate",
    "DeliverableUpdate",
    # risk
    "RiskType",
    "RiskSeverity",
    "EscalationStatus",
    "RiskStatus",
    "RiskBlocker",
    "RiskCreate",
    "RiskUpdate",
    # decision
    "DecisionStatus",
    "ArtifactType",
    "ImpactedArtifact",
    "Decision",
    "DecisionCreate",
    "DecisionResolve",
    # status_update
    "StatusScopeType",
    "StatusUpdate",
    # capability (v2 stub)
    "CapabilityMaturity",
    "RoadmapStatus",
    "Capability",
]
