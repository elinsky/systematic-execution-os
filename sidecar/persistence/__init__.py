"""Repository pattern persistence layer.

Each repository provides async CRUD operations for one entity type,
using the SQLAlchemy async session. Repositories are injected into services.
"""

from sidecar.persistence.pm_coverage import PMCoverageRepository
from sidecar.persistence.pm_need import PMNeedRepository
from sidecar.persistence.project import ProjectRepository
from sidecar.persistence.milestone import MilestoneRepository
from sidecar.persistence.risk import RiskRepository
from sidecar.persistence.decision import DecisionRepository

__all__ = [
    "PMCoverageRepository",
    "PMNeedRepository",
    "ProjectRepository",
    "MilestoneRepository",
    "RiskRepository",
    "DecisionRepository",
]
