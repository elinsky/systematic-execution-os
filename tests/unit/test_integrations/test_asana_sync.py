"""Unit tests for sidecar/integrations/asana_sync.py.

Uses an in-memory SQLite database (db_session fixture from conftest.py).
Tests the upsert (insert + conflict update) behaviour and source-of-truth
rules enforced during pull sync.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from sidecar.db.milestone import MilestoneTable
from sidecar.db.pm_coverage import PMCoverageTable
from sidecar.db.pm_need import PMNeedTable
from sidecar.db.project import ProjectTable
from sidecar.db.risk import RiskTable
from sidecar.integrations.asana.mapper import AsanaFieldConfig
from sidecar.integrations.asana_sync import (
    find_milestone_by_gid,
    find_pm_coverage_by_gid,
    find_pm_need_by_gid,
    find_project_by_gid,
    find_risk_by_gid,
    pull_sync_milestone,
    pull_sync_pm_coverage_task,
    pull_sync_pm_need_task,
    pull_sync_project,
    pull_sync_risk,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def field_cfg() -> AsanaFieldConfig:
    """Minimal field config with GIDs for all relevant fields."""
    return AsanaFieldConfig(
        health_gid="health-gid",
        region_gid="region-gid",
        last_touchpoint_gid="touchpoint-gid",
        need_category_gid="cat-gid",
        urgency_gid="urgency-gid",
        project_type_gid="projtype-gid",
        priority_gid="priority-gid",
        milestone_status_gid="ms-status-gid",
        milestone_confidence_gid="ms-conf-gid",
        risk_type_gid="risk-type-gid",
        severity_gid="severity-gid",
        escalation_status_gid="esc-gid",
    )


def _make_task(
    gid: str = "task-gid-1",
    name: str = "Test Task",
    section_name: str = "New",
    completed: bool = False,
    custom_fields: list | None = None,
    assignee_name: str | None = None,
    due_on: str | None = None,
    notes: str | None = None,
    created_at: str = "2025-01-10T00:00:00.000Z",
    completed_at: str | None = None,
) -> dict:
    """Build a minimal Asana task dict."""
    task: dict = {
        "gid": gid,
        "name": name,
        "completed": completed,
        "completed_at": completed_at,
        "created_at": created_at,
        "due_on": due_on,
        "notes": notes,
        "memberships": [{"section": {"name": section_name}}],
        "custom_fields": custom_fields or [],
    }
    if assignee_name:
        task["assignee"] = {"name": assignee_name}
    else:
        task["assignee"] = None
    return task


def _enum_cf(gid: str, name: str) -> dict:
    return {"gid": gid, "enum_value": {"name": name}, "text_value": None}


def _text_cf(gid: str, value: str) -> dict:
    return {"gid": gid, "enum_value": None, "text_value": value}


# ---------------------------------------------------------------------------
# pull_sync_pm_coverage_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pm_coverage_insert(db_session, field_cfg):
    task = _make_task(gid="cov-1", name="Jane Doe", section_name="Pipeline")
    inserted = await pull_sync_pm_coverage_task(db_session, task, "pm-jane", field_cfg)
    await db_session.commit()
    assert inserted is True

    row = await db_session.get(PMCoverageTable, "pm-jane")
    assert row is not None
    assert row.pm_name == "Jane Doe"
    assert row.onboarding_stage == "pipeline"
    assert row.asana_gid == "cov-1"


@pytest.mark.asyncio
async def test_pm_coverage_upsert_updates_asana_fields(db_session, field_cfg):
    task1 = _make_task(gid="cov-1", name="Jane Doe", section_name="Pipeline")
    await pull_sync_pm_coverage_task(db_session, task1, "pm-jane", field_cfg)
    await db_session.commit()

    # Second sync with updated stage
    task2 = _make_task(gid="cov-1", name="Jane Doe Updated", section_name="Live")
    inserted = await pull_sync_pm_coverage_task(db_session, task2, "pm-jane", field_cfg)
    await db_session.commit()

    assert inserted is False
    await db_session.refresh(await db_session.get(PMCoverageTable, "pm-jane"))
    row = await db_session.get(PMCoverageTable, "pm-jane")
    assert row.pm_name == "Jane Doe Updated"
    assert row.onboarding_stage == "live"


@pytest.mark.asyncio
async def test_pm_coverage_health_from_custom_field(db_session, field_cfg):
    task = _make_task(
        gid="cov-2",
        name="Bob",
        section_name="UAT",
        custom_fields=[_enum_cf("health-gid", "Yellow")],
    )
    await pull_sync_pm_coverage_task(db_session, task, "pm-bob", field_cfg)
    await db_session.commit()

    row = await db_session.get(PMCoverageTable, "pm-bob")
    assert row.health_status == "yellow"


# ---------------------------------------------------------------------------
# pull_sync_pm_need_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pm_need_insert(db_session, field_cfg):
    task = _make_task(gid="need-1", name="DMA Access", section_name="New")
    inserted = await pull_sync_pm_need_task(db_session, task, "n-1", "pm-jane", field_cfg)
    await db_session.commit()
    assert inserted is True

    row = await db_session.get(PMNeedTable, "n-1")
    assert row is not None
    assert row.title == "DMA Access"
    assert row.status == "new"     # D1: status from section
    assert row.asana_gid == "need-1"


@pytest.mark.asyncio
async def test_pm_need_status_driven_by_section(db_session, field_cfg):
    """D1: status is derived from Asana section, not custom field."""
    task = _make_task(
        gid="need-2",
        name="Broker Connectivity",
        section_name="In Progress",
    )
    await pull_sync_pm_need_task(db_session, task, "n-2", "pm-bob", field_cfg)
    await db_session.commit()

    row = await db_session.get(PMNeedTable, "n-2")
    assert row.status == "in_progress"


@pytest.mark.asyncio
async def test_pm_need_upsert_preserves_sidecar_fields(db_session, field_cfg):
    """Upsert must not overwrite pm_id (sidecar-owned relational field)."""
    task = _make_task(gid="need-3", name="Historical Data", section_name="Triaged")
    await pull_sync_pm_need_task(db_session, task, "n-3", "pm-jane", field_cfg)
    await db_session.commit()

    # Second sync for same need_id but different title
    task2 = _make_task(gid="need-3", name="Historical Data (updated)", section_name="Delivered")
    inserted = await pull_sync_pm_need_task(db_session, task2, "n-3", "pm-jane", field_cfg)
    await db_session.commit()

    assert inserted is False
    row = await db_session.get(PMNeedTable, "n-3")
    assert row.title == "Historical Data (updated)"
    assert row.status == "delivered"
    assert row.pm_id == "pm-jane"   # preserved


@pytest.mark.asyncio
async def test_pm_need_category_from_custom_field(db_session, field_cfg):
    task = _make_task(
        gid="need-4",
        name="DMA",
        section_name="New",
        custom_fields=[_enum_cf("cat-gid", "Execution")],
    )
    await pull_sync_pm_need_task(db_session, task, "n-4", "pm-x", field_cfg)
    await db_session.commit()

    row = await db_session.get(PMNeedTable, "n-4")
    assert row.category == "execution"


# ---------------------------------------------------------------------------
# pull_sync_project
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_insert(db_session, field_cfg):
    project = {
        "gid": "proj-gid-1",
        "name": "Onboarding - Jane Doe",
        "owner": {"name": "Alice"},
        "start_on": "2025-01-01",
        "due_on": "2026-06-01",
        "current_status": {"color": "green", "title": "On Track"},
        "custom_fields": [],
    }
    inserted = await pull_sync_project(db_session, project, "proj-1", field_cfg)
    await db_session.commit()
    assert inserted is True

    row = await db_session.get(ProjectTable, "proj-1")
    assert row is not None
    assert row.name == "Onboarding - Jane Doe"
    assert row.health_status == "green"
    assert row.asana_gid == "proj-gid-1"


@pytest.mark.asyncio
async def test_project_upsert_updates_health_and_status(db_session, field_cfg):
    project1 = {
        "gid": "proj-gid-2",
        "name": "Capability Build",
        "owner": None,
        "start_on": None,
        "due_on": None,
        "current_status": {"color": "green", "title": ""},
        "custom_fields": [],
    }
    await pull_sync_project(db_session, project1, "proj-2", field_cfg)
    await db_session.commit()

    project2 = {
        "gid": "proj-gid-2",
        "name": "Capability Build",
        "owner": None,
        "start_on": None,
        "due_on": None,
        "current_status": {"color": "red", "title": ""},
        "custom_fields": [],
    }
    inserted = await pull_sync_project(db_session, project2, "proj-2", field_cfg)
    await db_session.commit()

    assert inserted is False
    row = await db_session.get(ProjectTable, "proj-2")
    assert row.health_status == "red"


# ---------------------------------------------------------------------------
# pull_sync_milestone
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_milestone_insert(db_session, field_cfg):
    task = _make_task(
        gid="ms-gid-1",
        name="Kickoff",
        due_on="2026-03-15",
        notes="Kickoff completed when kickoff meeting held.",
    )
    inserted = await pull_sync_milestone(db_session, task, "ms-1", "proj-1", field_cfg)
    await db_session.commit()
    assert inserted is True

    row = await db_session.get(MilestoneTable, "ms-1")
    assert row is not None
    assert row.name == "Kickoff"
    assert row.status == "not_started"
    assert row.acceptance_criteria == "Kickoff completed when kickoff meeting held."


@pytest.mark.asyncio
async def test_milestone_completed_overrides_status(db_session, field_cfg):
    """D1 analogue: completed=True must set status=complete regardless of custom field."""
    task = _make_task(
        gid="ms-gid-2",
        name="Go-Live Ready",
        completed=True,
        custom_fields=[_enum_cf("ms-status-gid", "At Risk")],
    )
    await pull_sync_milestone(db_session, task, "ms-2", "proj-1", field_cfg)
    await db_session.commit()

    row = await db_session.get(MilestoneTable, "ms-2")
    assert row.status == "complete"


@pytest.mark.asyncio
async def test_milestone_confidence_from_custom_field(db_session, field_cfg):
    task = _make_task(
        gid="ms-gid-3",
        name="UAT Complete",
        custom_fields=[_enum_cf("ms-conf-gid", "Low")],
    )
    await pull_sync_milestone(db_session, task, "ms-3", "proj-1", field_cfg)
    await db_session.commit()

    row = await db_session.get(MilestoneTable, "ms-3")
    assert row.confidence == "low"


@pytest.mark.asyncio
async def test_milestone_upsert(db_session, field_cfg):
    task1 = _make_task(gid="ms-gid-4", name="Requirements", due_on="2026-02-01")
    await pull_sync_milestone(db_session, task1, "ms-4", "proj-1", field_cfg)
    await db_session.commit()

    task2 = _make_task(gid="ms-gid-4", name="Requirements Confirmed", due_on="2026-02-10")
    inserted = await pull_sync_milestone(db_session, task2, "ms-4", "proj-1", field_cfg)
    await db_session.commit()

    assert inserted is False
    row = await db_session.get(MilestoneTable, "ms-4")
    assert row.name == "Requirements Confirmed"
    assert str(row.target_date) == "2026-02-10"


# ---------------------------------------------------------------------------
# pull_sync_risk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_risk_insert_open(db_session, field_cfg):
    task = _make_task(
        gid="risk-gid-1",
        name="Missing DMA broker",
        custom_fields=[
            _enum_cf("risk-type-gid", "Blocker"),
            _enum_cf("severity-gid", "High"),
        ],
    )
    inserted = await pull_sync_risk(db_session, task, "risk-1", field_cfg)
    await db_session.commit()
    assert inserted is True

    row = await db_session.get(RiskTable, "risk-1")
    assert row is not None
    assert row.title == "Missing DMA broker"
    assert row.risk_type == "blocker"
    assert row.severity == "high"
    assert row.status == "open"
    assert row.resolution_date is None


@pytest.mark.asyncio
async def test_risk_completed_maps_to_resolved(db_session, field_cfg):
    task = _make_task(
        gid="risk-gid-2",
        name="Data feed delay",
        completed=True,
        completed_at="2026-02-15T12:00:00.000Z",
    )
    await pull_sync_risk(db_session, task, "risk-2", field_cfg)
    await db_session.commit()

    row = await db_session.get(RiskTable, "risk-2")
    assert row.status == "resolved"
    assert row.resolution_date is not None


@pytest.mark.asyncio
async def test_risk_upsert_updates_severity(db_session, field_cfg):
    task1 = _make_task(
        gid="risk-gid-3",
        name="Latency risk",
        custom_fields=[_enum_cf("severity-gid", "Low")],
    )
    await pull_sync_risk(db_session, task1, "risk-3", field_cfg)
    await db_session.commit()

    task2 = _make_task(
        gid="risk-gid-3",
        name="Latency risk escalated",
        custom_fields=[_enum_cf("severity-gid", "Critical")],
    )
    inserted = await pull_sync_risk(db_session, task2, "risk-3", field_cfg)
    await db_session.commit()

    assert inserted is False
    row = await db_session.get(RiskTable, "risk-3")
    assert row.severity == "critical"
    assert row.title == "Latency risk escalated"


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_pm_coverage_by_gid(db_session, field_cfg):
    task = _make_task(gid="cov-lookup", name="Alice")
    await pull_sync_pm_coverage_task(db_session, task, "pm-alice", field_cfg)
    await db_session.commit()

    row = await find_pm_coverage_by_gid(db_session, "cov-lookup")
    assert row is not None
    assert row.pm_id == "pm-alice"

    none_row = await find_pm_coverage_by_gid(db_session, "nonexistent")
    assert none_row is None


@pytest.mark.asyncio
async def test_find_pm_need_by_gid(db_session, field_cfg):
    task = _make_task(gid="need-lookup", name="Connectivity")
    await pull_sync_pm_need_task(db_session, task, "n-lookup", "pm-x", field_cfg)
    await db_session.commit()

    row = await find_pm_need_by_gid(db_session, "need-lookup")
    assert row is not None
    assert row.need_id == "n-lookup"


@pytest.mark.asyncio
async def test_find_milestone_by_gid(db_session, field_cfg):
    task = _make_task(gid="ms-lookup", name="Milestone Lookup")
    await pull_sync_milestone(db_session, task, "ms-lookup-id", "proj-1", field_cfg)
    await db_session.commit()

    row = await find_milestone_by_gid(db_session, "ms-lookup")
    assert row is not None
    assert row.milestone_id == "ms-lookup-id"


@pytest.mark.asyncio
async def test_find_risk_by_gid(db_session, field_cfg):
    task = _make_task(gid="risk-lookup", name="Risk Lookup")
    await pull_sync_risk(db_session, task, "risk-lookup-id", field_cfg)
    await db_session.commit()

    row = await find_risk_by_gid(db_session, "risk-lookup")
    assert row is not None
    assert row.risk_id == "risk-lookup-id"


@pytest.mark.asyncio
async def test_find_project_by_gid(db_session, field_cfg):
    project = {
        "gid": "proj-lookup-gid",
        "name": "Lookup Project",
        "owner": None,
        "start_on": None,
        "due_on": None,
        "current_status": {},
        "custom_fields": [],
    }
    await pull_sync_project(db_session, project, "proj-lookup", field_cfg)
    await db_session.commit()

    row = await find_project_by_gid(db_session, "proj-lookup-gid")
    assert row is not None
    assert row.project_id == "proj-lookup"

    none_row = await find_project_by_gid(db_session, "nonexistent-gid")
    assert none_row is None
