"""Unit tests for sidecar/models/project.py."""

import pytest
from datetime import date
from pydantic import ValidationError

from sidecar.models.project import (
    Project,
    ProjectCreate,
    ProjectStatus,
    ProjectType,
    ProjectUpdate,
)
from sidecar.models.common import HealthStatus, Priority


class TestProject:
    def test_minimal_valid_project(self):
        proj = Project(
            project_id="proj-1",
            name="Onboarding - PM Jane Doe - US Equities Launch",
            project_type=ProjectType.PM_ONBOARDING,
        )
        assert proj.status == ProjectStatus.PLANNING
        assert proj.priority == Priority.MEDIUM
        assert proj.health == HealthStatus.UNKNOWN
        assert proj.primary_pm_ids == []
        assert proj.linked_pm_need_ids == []

    def test_full_project(self):
        proj = Project(
            project_id="proj-1",
            name="Onboarding - PM Jane - Launch",
            project_type=ProjectType.PM_ONBOARDING,
            business_objective="Get Jane live by Q2",
            success_criteria="PM trading live with all data feeds confirmed",
            primary_pm_ids=["pm-jane"],
            owner="Alice",
            status=ProjectStatus.ACTIVE,
            priority=Priority.HIGH,
            health=HealthStatus.GREEN,
            start_date=date(2026, 1, 1),
            target_date=date(2026, 6, 30),
            linked_pm_need_ids=["n-1"],
            linked_milestone_ids=["m-1"],
        )
        assert proj.owner == "Alice"
        assert proj.health == HealthStatus.GREEN

    def test_project_types(self):
        types = set(ProjectType)
        assert "pm_onboarding" in types
        assert "capability_build" in types
        assert len(types) == 5

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            Project(
                project_id="p-1",
                name="P",
                project_type=ProjectType.INVESTIGATION,
                unknown="bad",
            )


class TestProjectUpdate:
    def test_partial_update_status_only(self):
        update = ProjectUpdate(project_id="p-1", status=ProjectStatus.AT_RISK)
        assert update.status == ProjectStatus.AT_RISK
        assert update.health is None
        assert update.owner is None

    def test_partial_update_health_and_owner(self):
        update = ProjectUpdate(project_id="p-1", health=HealthStatus.RED, owner="Bob")
        assert update.health == HealthStatus.RED
        assert update.owner == "Bob"
