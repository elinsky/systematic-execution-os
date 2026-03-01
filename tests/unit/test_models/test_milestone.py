"""Unit tests for sidecar/models/milestone.py."""

import pytest
from datetime import date
from pydantic import ValidationError

from sidecar.models.milestone import (
    Milestone,
    MilestoneConfidence,
    MilestoneCreate,
    MilestoneStatus,
    MilestoneUpdate,
    STANDARD_ONBOARDING_MILESTONES,
)


class TestMilestone:
    def test_minimal_valid_milestone(self):
        m = Milestone(
            milestone_id="m-1",
            project_id="proj-1",
            name="PM Jane Doe - Go Live Ready",
        )
        assert m.status == MilestoneStatus.NOT_STARTED
        assert m.confidence == MilestoneConfidence.UNKNOWN

    def test_full_milestone(self):
        m = Milestone(
            milestone_id="m-1",
            project_id="proj-1",
            name="PM Jane Doe - UAT Complete",
            target_date=date(2026, 5, 15),
            owner="Alice",
            status=MilestoneStatus.IN_PROGRESS,
            confidence=MilestoneConfidence.HIGH,
            gating_conditions="All data feeds validated",
            acceptance_criteria="PM signs off on UAT report",
        )
        assert m.confidence == MilestoneConfidence.HIGH
        assert m.acceptance_criteria == "PM signs off on UAT report"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            Milestone(
                milestone_id="m-1",
                project_id="p-1",
                name="M",
                bad="field",
            )


class TestStandardOnboardingMilestones:
    def test_count(self):
        assert len(STANDARD_ONBOARDING_MILESTONES) == 10

    def test_contains_go_live(self):
        assert any("Go-Live" in m for m in STANDARD_ONBOARDING_MILESTONES)

    def test_contains_kickoff(self):
        assert STANDARD_ONBOARDING_MILESTONES[0] == "Kickoff"


class TestMilestoneUpdate:
    def test_partial_update(self):
        update = MilestoneUpdate(
            milestone_id="m-1",
            status=MilestoneStatus.AT_RISK,
            confidence=MilestoneConfidence.LOW,
        )
        assert update.status == MilestoneStatus.AT_RISK
        assert update.owner is None
