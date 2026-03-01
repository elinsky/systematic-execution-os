"""Unit tests for sidecar/models/pm_coverage.py."""

import pytest
from datetime import date
from pydantic import ValidationError

from sidecar.models.pm_coverage import (
    OnboardingStage,
    PMCoverageCreate,
    PMCoverageRecord,
    PMCoverageUpdate,
)
from sidecar.models.common import HealthStatus


class TestOnboardingStage:
    def test_all_stages_present(self):
        stages = set(OnboardingStage)
        assert "pipeline" in stages
        assert "live" in stages
        assert "steady_state" in stages
        assert len(stages) == 9

    def test_is_str_enum(self):
        assert OnboardingStage.LIVE == "live"


class TestPMCoverageRecord:
    def test_minimal_valid_record(self):
        record = PMCoverageRecord(pm_id="pm-test", pm_name="Test PM")
        assert record.pm_id == "pm-test"
        assert record.pm_name == "Test PM"
        assert record.onboarding_stage == OnboardingStage.PIPELINE
        assert record.health_status == HealthStatus.UNKNOWN
        assert record.linked_project_ids == []

    def test_full_record(self):
        record = PMCoverageRecord(
            pm_id="pm-jane",
            pm_name="Jane Doe",
            team_or_pod="US Equities",
            strategy_type="Long/Short",
            region="US",
            coverage_owner="Alice",
            onboarding_stage=OnboardingStage.UAT,
            go_live_target_date=date(2026, 6, 1),
            health_status=HealthStatus.YELLOW,
            last_touchpoint_date=date(2026, 2, 28),
            linked_project_ids=["proj-1", "proj-2"],
            notes="On track",
        )
        assert record.onboarding_stage == OnboardingStage.UAT
        assert record.health_status == HealthStatus.YELLOW
        assert len(record.linked_project_ids) == 2

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            PMCoverageRecord(pm_id="pm-x")  # missing pm_name

    def test_no_top_open_need_ids_field(self):
        # D5: derived fields removed from schema
        record = PMCoverageRecord(pm_id="pm-x", pm_name="X")
        assert not hasattr(record, "top_open_need_ids")
        assert not hasattr(record, "top_blocker_ids")

    def test_no_sync_state_field(self):
        # D6: SyncState enum removed; replaced by asana_gid + asana_synced_at
        record = PMCoverageRecord(pm_id="pm-x", pm_name="X")
        assert not hasattr(record, "sync_state")
        assert hasattr(record, "asana_gid")
        assert hasattr(record, "asana_synced_at")

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            PMCoverageRecord(pm_id="pm-x", pm_name="X", unknown_field="bad")


class TestPMCoverageCreate:
    def test_requires_pm_id_and_name(self):
        obj = PMCoverageCreate(pm_id="pm-new", pm_name="New PM")
        assert obj.pm_id == "pm-new"


class TestPMCoverageUpdate:
    def test_partial_update_only_stage(self):
        update = PMCoverageUpdate(
            pm_id="pm-jane",
            onboarding_stage=OnboardingStage.GO_LIVE_READY,
        )
        assert update.onboarding_stage == OnboardingStage.GO_LIVE_READY
        assert update.health_status is None

    def test_partial_update_only_health(self):
        update = PMCoverageUpdate(pm_id="pm-jane", health_status=HealthStatus.RED)
        assert update.health_status == HealthStatus.RED
        assert update.onboarding_stage is None
