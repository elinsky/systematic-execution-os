"""Risk / Blocker / Issue domain model.

Source of truth: Hybrid.
- Asana: task in a dedicated Risks & Blockers project.
- Sidecar: severity, impact linkages, escalation state, age tracking.
"""

from datetime import date
from enum import StrEnum
from typing import Optional
from pydantic import Field, model_validator

from .common import AsanaLinkedRecord


class RiskType(StrEnum):
    RISK = "risk"
    BLOCKER = "blocker"
    ISSUE = "issue"


class RiskSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EscalationStatus(StrEnum):
    NONE = "none"
    WATCHING = "watching"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class RiskStatus(StrEnum):
    OPEN = "open"
    IN_MITIGATION = "in_mitigation"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"
    CLOSED = "closed"


class RiskBlocker(AsanaLinkedRecord):
    """A trackable object for threats to outcomes, dates, or confidence.

    Naming convention: '[Scope] - [Short Problem]'
    Example: 'PM Jane Doe - Historical Data Feed Delayed'

    Alert threshold defaults (configurable via settings):
    - age_days > 7 days while OPEN → trigger escalation watch
    - severity CRITICAL + age_days > 3 → immediate escalation flag
    """

    risk_id: str = Field(description="Internal sidecar identifier")
    title: str
    risk_type: RiskType = RiskType.RISK
    severity: RiskSeverity = RiskSeverity.MEDIUM
    status: RiskStatus = RiskStatus.OPEN
    owner: Optional[str] = None
    date_opened: date
    resolution_date: Optional[date] = None

    # Impact linkages
    impacted_pm_ids: list[str] = Field(default_factory=list)
    impacted_project_ids: list[str] = Field(default_factory=list)
    impacted_milestone_ids: list[str] = Field(default_factory=list)

    # Escalation
    escalation_status: EscalationStatus = EscalationStatus.NONE
    mitigation_plan: Optional[str] = None
    notes: Optional[str] = None

    @property
    def age_days(self) -> Optional[int]:
        """Computed from date_opened to today; use at query time."""
        from datetime import date as date_type
        if self.date_opened:
            return (date_type.today() - self.date_opened).days
        return None


class RiskCreate(RiskBlocker):
    risk_id: str
    title: str
    date_opened: date
    risk_type: RiskType
    severity: RiskSeverity


class RiskUpdate(AsanaLinkedRecord):
    risk_id: str
    status: Optional[RiskStatus] = None
    severity: Optional[RiskSeverity] = None
    escalation_status: Optional[EscalationStatus] = None
    owner: Optional[str] = None
    mitigation_plan: Optional[str] = None
    resolution_date: Optional[date] = None
    notes: Optional[str] = None
