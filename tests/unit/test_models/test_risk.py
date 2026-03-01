"""Unit tests for sidecar/models/risk.py."""

import pytest
from datetime import date
from pydantic import ValidationError

from sidecar.models.risk import (
    EscalationStatus,
    RiskBlocker,
    RiskCreate,
    RiskSeverity,
    RiskStatus,
    RiskType,
    RiskUpdate,
)


class TestRiskBlocker:
    def test_minimal_valid_risk(self):
        risk = RiskBlocker(
            risk_id="r-1",
            title="PM Jane Doe - Historical Data Feed Delayed",
            date_opened=date(2026, 2, 1),
        )
        assert risk.risk_type == RiskType.RISK
        assert risk.severity == RiskSeverity.MEDIUM
        assert risk.status == RiskStatus.OPEN
        assert risk.escalation_status == EscalationStatus.NONE
        assert risk.impacted_pm_ids == []
        assert risk.impacted_project_ids == []

    def test_age_days_computed(self):
        risk = RiskBlocker(
            risk_id="r-1",
            title="T",
            date_opened=date(2026, 2, 1),
        )
        # age_days is a computed property; just verify it returns an int
        assert isinstance(risk.age_days, int)
        assert risk.age_days >= 0

    def test_age_days_not_in_serialized_fields(self):
        # age_days is a @property, should NOT appear in model fields
        assert "age_days" not in RiskBlocker.model_fields

    def test_blocker_type(self):
        risk = RiskBlocker(
            risk_id="r-1",
            title="T",
            date_opened=date(2026, 1, 1),
            risk_type=RiskType.BLOCKER,
            severity=RiskSeverity.CRITICAL,
        )
        assert risk.risk_type == RiskType.BLOCKER
        assert risk.severity == RiskSeverity.CRITICAL

    def test_impact_linkages(self):
        risk = RiskBlocker(
            risk_id="r-1",
            title="T",
            date_opened=date(2026, 1, 1),
            impacted_pm_ids=["pm-jane"],
            impacted_project_ids=["proj-1"],
            impacted_milestone_ids=["m-1"],
        )
        assert "pm-jane" in risk.impacted_pm_ids
        assert "proj-1" in risk.impacted_project_ids

    def test_missing_required_date_opened(self):
        with pytest.raises(ValidationError):
            RiskBlocker(risk_id="r-1", title="T")

    def test_no_sync_state_field(self):
        risk = RiskBlocker(risk_id="r-1", title="T", date_opened=date(2026, 1, 1))
        assert not hasattr(risk, "sync_state")
        assert hasattr(risk, "asana_gid")


class TestRiskUpdate:
    def test_partial_update(self):
        update = RiskUpdate(
            risk_id="r-1",
            status=RiskStatus.IN_MITIGATION,
            escalation_status=EscalationStatus.ESCALATED,
        )
        assert update.status == RiskStatus.IN_MITIGATION
        assert update.owner is None

    def test_resolution_update(self):
        update = RiskUpdate(
            risk_id="r-1",
            status=RiskStatus.RESOLVED,
            resolution_date=date(2026, 3, 1),
        )
        assert update.resolution_date == date(2026, 3, 1)
