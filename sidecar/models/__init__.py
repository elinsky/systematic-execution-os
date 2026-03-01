"""Sidecar domain models.

All Pydantic v2 domain models for the BAM Systematic Execution OS sidecar.
"""

from .common import (
    SidecarBaseModel,
    AsanaLinkedRecord,
    HealthStatus,
    Priority,
    Urgency,
    BusinessImpact,
    SyncState,
)
from .pm_coverage import (
    OnboardingStage,
    PMCoverageRecord,
    PMCoverageCreate,
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
    ProjectType,
    ProjectStatus,
    Project,
    ProjectCreate,
    ProjectUpdate,
)
from .milestone import (
    MilestoneStatus,
    MilestoneConfidence,
    STANDARD_ONBOARDING_MILESTONES,
    Milestone,
    MilestoneCreate,
    MilestoneUpdate,
)
from .deliverable import (
    DeliverableStatus,
    Deliverable,
    DeliverableCreate,
    DeliverableUpdate,
)
from .risk import (
    RiskType,
    RiskSeverity,
    EscalationStatus,
    RiskStatus,
    RiskBlocker,
    RiskCreate,
    RiskUpdate,
)
from .decision import (
    DecisionStatus,
    ArtifactType,
    ImpactedArtifact,
    Decision,
    DecisionCreate,
    DecisionResolve,
)
from .status_update import (
    StatusScopeType,
    StatusUpdate,
)
from .capability import (
    CapabilityMaturity,
    RoadmapStatus,
    Capability,
)

__all__ = [
    # common
    "SidecarBaseModel",
    "AsanaLinkedRecord",
    "HealthStatus",
    "Priority",
    "Urgency",
    "BusinessImpact",
    "SyncState",
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
