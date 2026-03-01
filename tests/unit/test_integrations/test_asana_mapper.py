"""Tests for AsanaMapper — Asana API payload ↔ domain model translation.

All tests are pure (no HTTP calls). They verify that raw Asana API dicts
are correctly translated into domain models and vice versa.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from sidecar.integrations.asana.mapper import AsanaFieldConfig, AsanaMapper
from sidecar.models import (
    HealthStatus,
    MilestoneConfidence,
    MilestoneStatus,
    NeedCategory,
    NeedStatus,
    OnboardingStage,
    ProjectStatus,
    ProjectType,
    RiskSeverity,
    RiskStatus,
    RiskType,
    Urgency,
    BusinessImpact,
    Priority,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def field_cfg() -> AsanaFieldConfig:
    """A realistic field config with GIDs for all supported fields."""
    return AsanaFieldConfig(
        onboarding_stage_gid="gid-stage",
        health_gid="gid-health",
        region_gid="gid-region",
        last_touchpoint_gid="gid-touchpoint",
        need_category_gid="gid-category",
        urgency_gid="gid-urgency",
        business_impact_gid="gid-impact",
        need_status_gid="gid-need-status",
        resolution_path_gid="gid-resolution",
        project_type_gid="gid-proj-type",
        priority_gid="gid-priority",
        project_health_gid="gid-proj-health",
        milestone_status_gid="gid-ms-status",
        milestone_confidence_gid="gid-ms-confidence",
        risk_type_gid="gid-risk-type",
        severity_gid="gid-severity",
        escalation_status_gid="gid-escalation",
        risk_status_gid="gid-risk-status",
        pm_coverage_project_gid="proj-pm-coverage",
        pm_needs_project_gid="proj-pm-needs",
        risks_project_gid="proj-risks",
    )


@pytest.fixture
def mapper(field_cfg: AsanaFieldConfig) -> AsanaMapper:
    return AsanaMapper(field_cfg)


def make_custom_fields(*args: tuple[str, str, str]) -> list[dict]:
    """Build a custom_fields list. Each arg is (gid, field_type, value)."""
    result = []
    for gid, field_type, value in args:
        if field_type == "enum":
            result.append({"gid": gid, "enum_value": {"gid": f"{gid}-val", "name": value}})
        elif field_type == "text":
            result.append({"gid": gid, "text_value": value})
        elif field_type == "date":
            result.append({"gid": gid, "date_value": {"date": value}})
    return result


# ---------------------------------------------------------------------------
# PM Coverage — from_asana_pm_coverage
# ---------------------------------------------------------------------------

class TestFromAsanaPmCoverage:
    def test_basic_fields(self, mapper: AsanaMapper):
        task = {
            "gid": "task-pm-1",
            "name": "Jane Doe",
            "assignee": {"gid": "user-1", "name": "Coverage Lead"},
            "due_on": "2026-06-01",
            "custom_fields": make_custom_fields(
                ("gid-health", "enum", "green"),
                ("gid-region", "text", "AMER"),
            ),
            "memberships": [
                {"section": {"gid": "sec-1", "name": "Onboarding In Progress"}, "project": {"gid": "proj-board"}}
            ],
        }
        result = mapper.from_asana_pm_coverage(task, pm_id="pm-jane")
        assert result.pm_id == "pm-jane"
        assert result.pm_name == "Jane Doe"
        assert result.health_status == HealthStatus.GREEN
        assert result.region == "AMER"
        assert result.coverage_owner == "Coverage Lead"
        assert result.onboarding_stage == OnboardingStage.ONBOARDING_IN_PROGRESS
        assert result.asana_gid == "task-pm-1"
        assert result.asana_synced_at is not None

    def test_stage_from_section_pipeline(self, mapper: AsanaMapper):
        task = {
            "gid": "t1", "name": "PM X",
            "custom_fields": [],
            "memberships": [{"section": {"gid": "s1", "name": "Pipeline"}, "project": {"gid": "p1"}}],
        }
        result = mapper.from_asana_pm_coverage(task, pm_id="pm-x")
        assert result.onboarding_stage == OnboardingStage.PIPELINE

    def test_stage_from_section_live(self, mapper: AsanaMapper):
        task = {
            "gid": "t2", "name": "PM Y",
            "custom_fields": [],
            "memberships": [{"section": {"gid": "s2", "name": "Live"}, "project": {"gid": "p1"}}],
        }
        result = mapper.from_asana_pm_coverage(task, pm_id="pm-y")
        assert result.onboarding_stage == OnboardingStage.LIVE

    def test_unknown_section_defaults_to_pipeline(self, mapper: AsanaMapper):
        task = {
            "gid": "t3", "name": "PM Z",
            "custom_fields": [],
            "memberships": [{"section": {"gid": "s3", "name": "Unknown Stage"}, "project": {"gid": "p1"}}],
        }
        result = mapper.from_asana_pm_coverage(task, pm_id="pm-z")
        assert result.onboarding_stage == OnboardingStage.PIPELINE

    def test_no_memberships_gives_pipeline(self, mapper: AsanaMapper):
        task = {"gid": "t4", "name": "PM W", "custom_fields": [], "memberships": []}
        result = mapper.from_asana_pm_coverage(task, pm_id="pm-w")
        assert result.onboarding_stage == OnboardingStage.PIPELINE

    def test_missing_health_defaults_to_unknown(self, mapper: AsanaMapper):
        task = {"gid": "t5", "name": "PM V", "custom_fields": [], "memberships": []}
        result = mapper.from_asana_pm_coverage(task, pm_id="pm-v")
        assert result.health_status == HealthStatus.UNKNOWN


# ---------------------------------------------------------------------------
# PM Need — from_asana_pm_need
# ---------------------------------------------------------------------------

class TestFromAsanaPmNeed:
    def test_basic_fields(self, mapper: AsanaMapper):
        task = {
            "gid": "task-need-1",
            "name": "Jane Doe - Execution - DMA via Goldman",
            "assignee": {"gid": "user-1", "name": "Jane Doe"},
            "due_on": "2026-04-30",
            "created_at": "2026-03-01T10:00:00.000Z",
            "notes": "Need DMA access for US equities.",
            "custom_fields": make_custom_fields(
                ("gid-category", "enum", "execution"),
                ("gid-urgency", "enum", "this_month"),
                ("gid-impact", "enum", "high"),
            ),
            "memberships": [{"section": {"gid": "s1", "name": "Triaged"}, "project": {"gid": "proj-needs"}}],
        }
        result = mapper.from_asana_pm_need(task, pm_need_id="need-1", pm_id="pm-jane")
        assert result.pm_need_id == "need-1"
        assert result.pm_id == "pm-jane"
        assert result.title == "Jane Doe - Execution - DMA via Goldman"
        assert result.category == NeedCategory.EXECUTION
        assert result.urgency == Urgency.THIS_MONTH
        assert result.business_impact == BusinessImpact.HIGH
        assert result.status == NeedStatus.TRIAGED
        assert result.desired_by_date == date(2026, 4, 30)
        assert result.notes == "Need DMA access for US equities."
        assert result.asana_gid == "task-need-1"

    def test_status_driven_by_section(self, mapper: AsanaMapper):
        task = {
            "gid": "t2", "name": "Need X",
            "created_at": "2026-03-01T00:00:00.000Z",
            "custom_fields": [],
            "memberships": [{"section": {"gid": "s2", "name": "Blocked"}, "project": {"gid": "p2"}}],
        }
        result = mapper.from_asana_pm_need(task, pm_need_id="n2", pm_id="pm-x")
        assert result.status == NeedStatus.BLOCKED

    def test_delivered_section(self, mapper: AsanaMapper):
        task = {
            "gid": "t3", "name": "Need Y",
            "created_at": "2026-02-01T00:00:00.000Z",
            "custom_fields": [],
            "memberships": [{"section": {"gid": "s3", "name": "Delivered"}, "project": {"gid": "p2"}}],
        }
        result = mapper.from_asana_pm_need(task, pm_need_id="n3", pm_id="pm-y")
        assert result.status == NeedStatus.DELIVERED

    def test_unknown_category_defaults_to_other(self, mapper: AsanaMapper):
        task = {
            "gid": "t4", "name": "Need Z",
            "created_at": "2026-01-01T00:00:00.000Z",
            "custom_fields": make_custom_fields(("gid-category", "enum", "unknown_category")),
            "memberships": [],
        }
        result = mapper.from_asana_pm_need(task, pm_need_id="n4", pm_id="pm-z")
        assert result.category == NeedCategory.OTHER


# ---------------------------------------------------------------------------
# Project — from_asana_project
# ---------------------------------------------------------------------------

class TestFromAsanaProject:
    def test_basic_project(self, mapper: AsanaMapper):
        project = {
            "gid": "proj-1",
            "name": "Onboarding - Jane Doe - US Equities",
            "owner": {"gid": "user-1", "name": "PMO Lead"},
            "start_on": "2026-02-01",
            "due_on": "2026-06-01",
            "current_status": {"color": "green", "title": "On Track"},
            "custom_fields": make_custom_fields(
                ("gid-proj-type", "enum", "pm_onboarding"),
                ("gid-priority", "enum", "high"),
            ),
        }
        result = mapper.from_asana_project(project, project_id="p-123")
        assert result.project_id == "p-123"
        assert result.name == "Onboarding - Jane Doe - US Equities"
        assert result.project_type == ProjectType.PM_ONBOARDING
        assert result.priority == Priority.HIGH
        assert result.status == ProjectStatus.ACTIVE
        assert result.health == HealthStatus.GREEN
        assert result.start_date == date(2026, 2, 1)
        assert result.target_date == date(2026, 6, 1)
        assert result.asana_gid == "proj-1"

    def test_red_project_maps_to_at_risk(self, mapper: AsanaMapper):
        project = {
            "gid": "proj-2", "name": "At Risk Project",
            "current_status": {"color": "red", "title": "At Risk"},
            "custom_fields": [],
        }
        result = mapper.from_asana_project(project, project_id="p-2")
        assert result.status == ProjectStatus.AT_RISK
        assert result.health == HealthStatus.RED

    def test_no_status_defaults_to_planning(self, mapper: AsanaMapper):
        project = {
            "gid": "proj-3", "name": "New Project",
            "current_status": None,
            "custom_fields": [],
        }
        result = mapper.from_asana_project(project, project_id="p-3")
        assert result.status == ProjectStatus.PLANNING
        assert result.health == HealthStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Milestone — from_asana_milestone
# ---------------------------------------------------------------------------

class TestFromAsanaMilestone:
    def test_incomplete_milestone(self, mapper: AsanaMapper):
        task = {
            "gid": "ms-1",
            "name": "Jane Doe - Go Live Ready",
            "assignee": {"gid": "u1", "name": "PMO"},
            "due_on": "2026-05-15",
            "completed": False,
            "completed_at": None,
            "resource_subtype": "milestone",
            "notes": "All data feeds verified. Execution tested.",
            "custom_fields": make_custom_fields(
                ("gid-ms-confidence", "enum", "high"),
                ("gid-ms-status", "enum", "in_progress"),
            ),
        }
        result = mapper.from_asana_milestone(task, milestone_id="m-1", project_id="p-1")
        assert result.milestone_id == "m-1"
        assert result.name == "Jane Doe - Go Live Ready"
        assert result.status == MilestoneStatus.IN_PROGRESS
        assert result.confidence == MilestoneConfidence.HIGH
        assert result.target_date == date(2026, 5, 15)
        assert result.acceptance_criteria == "All data feeds verified. Execution tested."

    def test_completed_milestone_overrides_status(self, mapper: AsanaMapper):
        task = {
            "gid": "ms-2", "name": "Kickoff",
            "due_on": "2026-03-01",
            "completed": True,
            "completed_at": "2026-03-01T09:00:00.000Z",
            "resource_subtype": "milestone",
            "notes": "",
            "custom_fields": make_custom_fields(
                ("gid-ms-status", "enum", "in_progress"),  # should be overridden
            ),
        }
        result = mapper.from_asana_milestone(task, milestone_id="m-2", project_id="p-1")
        # completed=True should always yield COMPLETE regardless of custom field
        assert result.status == MilestoneStatus.COMPLETE

    def test_unknown_confidence_defaults(self, mapper: AsanaMapper):
        task = {
            "gid": "ms-3", "name": "Requirements Confirmed",
            "due_on": None, "completed": False,
            "resource_subtype": "milestone",
            "custom_fields": [],
        }
        result = mapper.from_asana_milestone(task, milestone_id="m-3", project_id="p-1")
        assert result.confidence == MilestoneConfidence.UNKNOWN


# ---------------------------------------------------------------------------
# Risk — from_asana_risk
# ---------------------------------------------------------------------------

class TestFromAsanaRisk:
    def test_open_blocker(self, mapper: AsanaMapper):
        task = {
            "gid": "risk-1",
            "name": "Jane Doe - Historical Data Feed Delayed",
            "assignee": {"gid": "u1", "name": "PMO"},
            "created_at": "2026-02-20T10:00:00.000Z",
            "completed": False,
            "completed_at": None,
            "notes": "Bloomberg feed not yet configured.",
            "custom_fields": make_custom_fields(
                ("gid-risk-type", "enum", "blocker"),
                ("gid-severity", "enum", "high"),
                ("gid-escalation", "enum", "watching"),
            ),
        }
        result = mapper.from_asana_risk(task, risk_id="r-1")
        assert result.risk_id == "r-1"
        assert result.risk_type == RiskType.BLOCKER
        assert result.severity == RiskSeverity.HIGH
        assert result.escalation_status.value == "watching"
        assert result.status == RiskStatus.OPEN
        assert result.date_opened == date(2026, 2, 20)
        assert result.resolution_date is None
        assert result.mitigation_plan == "Bloomberg feed not yet configured."

    def test_completed_task_maps_to_resolved(self, mapper: AsanaMapper):
        task = {
            "gid": "risk-2", "name": "Resolved Issue",
            "created_at": "2026-01-15T00:00:00.000Z",
            "completed": True,
            "completed_at": "2026-02-01T12:00:00.000Z",
            "custom_fields": [],
        }
        result = mapper.from_asana_risk(task, risk_id="r-2")
        assert result.status == RiskStatus.RESOLVED
        assert result.resolution_date == date(2026, 2, 1)

    def test_critical_severity(self, mapper: AsanaMapper):
        task = {
            "gid": "risk-3", "name": "Critical Blocker",
            "created_at": "2026-03-01T00:00:00.000Z",
            "completed": False,
            "custom_fields": make_custom_fields(("gid-severity", "enum", "critical")),
        }
        result = mapper.from_asana_risk(task, risk_id="r-3")
        assert result.severity == RiskSeverity.CRITICAL


# ---------------------------------------------------------------------------
# to_asana_* (outbound) tests
# ---------------------------------------------------------------------------

class TestToAsanaPayloads:
    def test_to_asana_pm_need_includes_custom_fields(self, mapper: AsanaMapper):
        body = mapper.to_asana_pm_need(
            title="Jane Doe - Market Data - Bloomberg Access",
            category=NeedCategory.MARKET_DATA,
            urgency=Urgency.THIS_WEEK,
            business_impact=BusinessImpact.HIGH,
            desired_by_date=date(2026, 4, 15),
            project_gid="proj-needs-gid",
            notes="Need Bloomberg terminal access.",
        )
        assert body["name"] == "Jane Doe - Market Data - Bloomberg Access"
        assert body["projects"] == ["proj-needs-gid"]
        assert body["due_on"] == "2026-04-15"
        assert body["notes"] == "Need Bloomberg terminal access."
        cf = body["custom_fields"]
        assert cf["gid-category"] == "market_data"
        assert cf["gid-urgency"] == "this_week"
        assert cf["gid-impact"] == "high"

    def test_to_asana_pm_need_omits_none_fields(self, mapper: AsanaMapper):
        body = mapper.to_asana_pm_need(
            title="Jane Doe - Infra - GPU Access",
            category=NeedCategory.INFRA,
            urgency=Urgency.BACKLOG,
            business_impact=BusinessImpact.MEDIUM,
            desired_by_date=None,
            project_gid="proj-needs-gid",
        )
        assert "due_on" not in body
        assert "notes" not in body

    def test_to_asana_milestone_sets_subtype(self, mapper: AsanaMapper):
        body = mapper.to_asana_milestone(
            name="PM Jane - Go Live Ready",
            project_gid="proj-123",
            target_date=date(2026, 6, 1),
            acceptance_criteria="All systems green.",
        )
        assert body["resource_subtype"] == "milestone"
        assert body["notes"] == "All systems green."
        assert body["due_on"] == "2026-06-01"

    def test_to_asana_project_includes_workspace(self, mapper: AsanaMapper):
        body = mapper.to_asana_project(
            name="Onboarding - Jane Doe - US Equities",
            project_type=ProjectType.PM_ONBOARDING,
            workspace_gid="workspace-abc",
            target_date=date(2026, 6, 30),
        )
        assert body["workspace"] == "workspace-abc"
        assert body["due_on"] == "2026-06-30"
        cf = body.get("custom_fields", {})
        assert cf.get("gid-proj-type") == "pm_onboarding"

    def test_to_asana_risk_includes_severity(self, mapper: AsanaMapper):
        body = mapper.to_asana_risk(
            title="PM Jane - Data Feed Delayed",
            risk_type=RiskType.BLOCKER,
            severity=RiskSeverity.CRITICAL,
            project_gid="proj-risks-gid",
            mitigation_plan="Escalate to tech lead.",
        )
        assert body["name"] == "PM Jane - Data Feed Delayed"
        cf = body["custom_fields"]
        assert cf["gid-risk-type"] == "blocker"
        assert cf["gid-severity"] == "critical"
        assert body["notes"] == "Escalate to tech lead."


# ---------------------------------------------------------------------------
# Edge cases — missing config GIDs
# ---------------------------------------------------------------------------

class TestMissingConfig:
    def test_mapper_with_empty_config_uses_defaults(self):
        empty_cfg = AsanaFieldConfig()  # all GIDs are None
        mapper = AsanaMapper(empty_cfg)
        task = {
            "gid": "t1", "name": "PM X",
            "custom_fields": [],
            "memberships": [],
        }
        result = mapper.from_asana_pm_coverage(task, pm_id="pm-x")
        # Should not raise; all fields fall back to defaults
        assert result.health_status == HealthStatus.UNKNOWN
        assert result.onboarding_stage == OnboardingStage.PIPELINE

    def test_to_asana_need_with_no_field_gids_omits_custom_fields(self):
        empty_cfg = AsanaFieldConfig()
        mapper = AsanaMapper(empty_cfg)
        body = mapper.to_asana_pm_need(
            title="Need",
            category=NeedCategory.EXECUTION,
            urgency=Urgency.THIS_MONTH,
            business_impact=BusinessImpact.MEDIUM,
            desired_by_date=None,
            project_gid="proj-1",
        )
        assert "custom_fields" not in body
