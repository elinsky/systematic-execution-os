"""Tests for model serialization / deserialization patterns.

Verifies that models round-trip cleanly through JSON (the primary
transport for API responses) and can be reconstructed from ORM attributes.
"""

from datetime import date

from sidecar.models.pm_coverage import OnboardingStage, PMCoverageRecord
from sidecar.models.pm_need import NeedCategory, PMNeed
from sidecar.models.risk import RiskBlocker, RiskSeverity, RiskType
from sidecar.models.decision import Decision, DecisionStatus
from sidecar.models.common import HealthStatus


class TestJsonRoundTrip:
    def test_pm_coverage_round_trip(self):
        record = PMCoverageRecord(
            pm_id="pm-jane",
            pm_name="Jane Doe",
            onboarding_stage=OnboardingStage.UAT,
            health_status=HealthStatus.GREEN,
            go_live_target_date=date(2026, 6, 1),
            linked_project_ids=["proj-1"],
        )
        serialized = record.model_dump(mode="json")
        restored = PMCoverageRecord.model_validate(serialized)
        assert restored.pm_id == record.pm_id
        assert restored.onboarding_stage == record.onboarding_stage
        assert restored.go_live_target_date == record.go_live_target_date
        assert restored.linked_project_ids == ["proj-1"]

    def test_pm_need_round_trip(self):
        need = PMNeed(
            pm_need_id="n-1",
            pm_id="pm-jane",
            title="Jane Doe - Execution - DMA via Goldman",
            requested_by="Jane Doe",
            date_raised=date(2026, 1, 15),
            category=NeedCategory.EXECUTION,
            linked_project_ids=["proj-1"],
        )
        serialized = need.model_dump(mode="json")
        restored = PMNeed.model_validate(serialized)
        assert restored.pm_need_id == need.pm_need_id
        assert restored.category == NeedCategory.EXECUTION
        assert restored.linked_project_ids == ["proj-1"]

    def test_risk_round_trip(self):
        risk = RiskBlocker(
            risk_id="r-1",
            title="PM Jane - Historical Data Delayed",
            date_opened=date(2026, 2, 1),
            risk_type=RiskType.BLOCKER,
            severity=RiskSeverity.HIGH,
        )
        serialized = risk.model_dump(mode="json")
        # age_days is a @property — should not appear in model_dump
        assert "age_days" not in serialized
        restored = RiskBlocker.model_validate(serialized)
        assert restored.risk_id == risk.risk_id
        assert restored.severity == RiskSeverity.HIGH

    def test_decision_round_trip(self):
        d = Decision(
            decision_id="d-1",
            title="Choose broker A over B",
            status=DecisionStatus.DECIDED,
            chosen_path="Broker A",
            approvers=["Alice", "Bob"],
        )
        serialized = d.model_dump(mode="json")
        restored = Decision.model_validate(serialized)
        assert restored.decision_id == d.decision_id
        assert restored.status == DecisionStatus.DECIDED
        assert restored.approvers == ["Alice", "Bob"]


class TestEnumSerialization:
    def test_enums_serialize_as_strings(self):
        record = PMCoverageRecord(pm_id="pm-x", pm_name="X")
        data = record.model_dump(mode="json")
        assert data["onboarding_stage"] == "pipeline"
        assert data["health_status"] == "unknown"

    def test_none_fields_in_dump(self):
        record = PMCoverageRecord(pm_id="pm-x", pm_name="X")
        data = record.model_dump()
        assert data["go_live_target_date"] is None
        assert data["asana_gid"] is None
