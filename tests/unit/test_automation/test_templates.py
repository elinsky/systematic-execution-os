"""Unit tests for sidecar/automation/templates.py.

Uses mock AsanaCRUD to verify:
- Project, section, milestone, and task creation calls are made correctly.
- Batch helpers are invoked with the right data.
- ProjectTemplateResult is populated with all returned GIDs.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sidecar.automation.templates import (
    ProjectTemplateResult,
    _ONBOARDING_SECTIONS,
    _ONBOARDING_SEED_TASKS,
    _CAPABILITY_SECTIONS,
    _CAPABILITY_MILESTONES,
    _CAPABILITY_SEED_TASKS,
    _STABILIZATION_SECTIONS,
    _STABILIZATION_SEED_TASKS,
    create_capability_build_project,
    create_pm_onboarding_project,
    create_stabilization_project,
)
from sidecar.models import ProjectType
from sidecar.integrations.asana.mapper import AsanaFieldConfig, AsanaMapper


# ---------------------------------------------------------------------------
# Mock factory
# ---------------------------------------------------------------------------

def _make_crud(project_gid: str = "proj-gid-1") -> MagicMock:
    """Return a MagicMock AsanaCRUD with sensible async defaults."""
    crud = MagicMock()
    crud._mapper = AsanaMapper(AsanaFieldConfig())

    # create_project returns a Project-like object with asana_gid
    project_mock = MagicMock()
    project_mock.asana_gid = project_gid
    crud.create_project = AsyncMock(return_value=project_mock)

    # batch_create_sections returns a list of {gid, name} dicts
    def _section_response(names: list[str]) -> list[dict]:
        return [{"gid": f"sec-{i}", "name": n} for i, n in enumerate(names)]

    async def batch_sections(project_gid, names):
        return _section_response(names)

    crud.batch_create_sections = AsyncMock(side_effect=batch_sections)

    # batch_create_tasks returns task dicts with gid and name
    _task_counter = [0]

    async def batch_tasks(bodies):
        results = []
        for b in bodies:
            _task_counter[0] += 1
            results.append({"gid": f"task-{_task_counter[0]}", "name": b.get("name", "")})
        return results

    crud.batch_create_tasks = AsyncMock(side_effect=batch_tasks)

    return crud


# ---------------------------------------------------------------------------
# PM Onboarding template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pm_onboarding_project_created():
    crud = _make_crud(project_gid="onb-gid-1")

    result = await create_pm_onboarding_project(
        crud=crud,
        project_id="proj-onb-1",
        pm_name="Jane Doe",
        strategy_label="US Equities",
        go_live_date=date(2026, 6, 1),
        team_gid="team-1",
        owner_gid="owner-1",
    )

    assert isinstance(result, ProjectTemplateResult)
    assert result.project_gid == "onb-gid-1"
    assert result.project_id == "proj-onb-1"


@pytest.mark.asyncio
async def test_pm_onboarding_project_name_format():
    crud = _make_crud()

    await create_pm_onboarding_project(
        crud=crud,
        project_id="proj-1",
        pm_name="Bob Smith",
        strategy_label="Macro",
    )

    call_kwargs = crud.create_project.call_args.kwargs
    assert call_kwargs["name"] == "Onboarding - Bob Smith - Macro"
    assert call_kwargs["project_type"] == ProjectType.PM_ONBOARDING


@pytest.mark.asyncio
async def test_pm_onboarding_all_sections_created():
    crud = _make_crud()

    result = await create_pm_onboarding_project(
        crud=crud,
        project_id="proj-1",
        pm_name="Jane",
        strategy_label="Equities",
    )

    assert len(result.section_gids) == len(_ONBOARDING_SECTIONS)
    for section_name in _ONBOARDING_SECTIONS:
        assert section_name in result.section_gids


@pytest.mark.asyncio
async def test_pm_onboarding_milestones_created():
    from sidecar.models.milestone import STANDARD_ONBOARDING_MILESTONES

    crud = _make_crud()

    result = await create_pm_onboarding_project(
        crud=crud,
        project_id="proj-1",
        pm_name="Alice",
        strategy_label="Rates",
    )

    assert len(result.milestone_gids) == len(STANDARD_ONBOARDING_MILESTONES)
    # Each milestone name should be prefixed with pm_name
    for full_name in result.milestone_gids:
        assert full_name.startswith("Alice - ")


@pytest.mark.asyncio
async def test_pm_onboarding_seed_tasks_created():
    crud = _make_crud()

    result = await create_pm_onboarding_project(
        crud=crud,
        project_id="proj-1",
        pm_name="Carlos",
        strategy_label="EM",
    )

    total_expected = sum(len(v) for v in _ONBOARDING_SEED_TASKS.values())
    assert len(result.task_gids) == total_expected


@pytest.mark.asyncio
async def test_pm_onboarding_go_live_date_on_milestones():
    """Go-live date is set only on Go-Live Ready and PM Live milestones."""
    crud = _make_crud()

    go_live = date(2026, 9, 1)
    mapper_calls: list[dict] = []

    orig_to_milestone = crud._mapper.to_asana_milestone

    def patched_to_milestone(**kwargs):
        mapper_calls.append(kwargs)
        return orig_to_milestone(**kwargs)

    crud._mapper.to_asana_milestone = patched_to_milestone

    await create_pm_onboarding_project(
        crud=crud,
        project_id="proj-1",
        pm_name="Jane",
        strategy_label="FX",
        go_live_date=go_live,
    )

    dated = [c for c in mapper_calls if c.get("target_date") == go_live]
    names_with_date = [c["name"] for c in dated]
    assert any("Go-Live Ready" in n for n in names_with_date)
    assert any("PM Live" in n for n in names_with_date)

    # Other milestones should have no date
    undated = [c for c in mapper_calls if c.get("target_date") is None]
    assert len(undated) > 0


# ---------------------------------------------------------------------------
# Capability Build template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_capability_build_project_created():
    crud = _make_crud(project_gid="cap-gid-1")

    result = await create_capability_build_project(
        crud=crud,
        project_id="proj-cap-1",
        capability_name="DMA Connectivity",
        phase_label="Phase 1",
    )

    assert result.project_gid == "cap-gid-1"
    assert result.project_id == "proj-cap-1"


@pytest.mark.asyncio
async def test_capability_build_project_name():
    crud = _make_crud()

    await create_capability_build_project(
        crud=crud,
        project_id="proj-cap-2",
        capability_name="Security Master",
        phase_label="Phase 2",
    )

    call_kwargs = crud.create_project.call_args.kwargs
    assert call_kwargs["name"] == "Capability - Security Master - Phase 2"
    assert call_kwargs["project_type"] == ProjectType.CAPABILITY_BUILD


@pytest.mark.asyncio
async def test_capability_build_sections_and_milestones():
    crud = _make_crud()

    result = await create_capability_build_project(
        crud=crud,
        project_id="proj-cap-3",
        capability_name="Alt Data Feed",
    )

    assert len(result.section_gids) == len(_CAPABILITY_SECTIONS)
    assert len(result.milestone_gids) == len(_CAPABILITY_MILESTONES)


@pytest.mark.asyncio
async def test_capability_build_seed_tasks():
    crud = _make_crud()

    result = await create_capability_build_project(
        crud=crud,
        project_id="proj-cap-4",
        capability_name="Execution Analytics",
    )

    total_expected = sum(len(v) for v in _CAPABILITY_SEED_TASKS.values())
    assert len(result.task_gids) == total_expected


# ---------------------------------------------------------------------------
# Stabilization template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stabilization_project_created():
    crud = _make_crud(project_gid="stab-gid-1")

    result = await create_stabilization_project(
        crud=crud,
        project_id="proj-stab-1",
        subject="Jane Doe",
    )

    assert result.project_gid == "stab-gid-1"
    assert result.project_id == "proj-stab-1"


@pytest.mark.asyncio
async def test_stabilization_project_name():
    crud = _make_crud()

    await create_stabilization_project(
        crud=crud,
        project_id="proj-stab-2",
        subject="Security Master",
    )

    call_kwargs = crud.create_project.call_args.kwargs
    assert call_kwargs["name"] == "Stabilization - Security Master - Post Live"
    assert call_kwargs["project_type"] == ProjectType.REMEDIATION


@pytest.mark.asyncio
async def test_stabilization_sections_and_no_milestones():
    crud = _make_crud()

    result = await create_stabilization_project(
        crud=crud,
        project_id="proj-stab-3",
        subject="Alt Data Feed",
    )

    assert len(result.section_gids) == len(_STABILIZATION_SECTIONS)
    assert result.milestone_gids == {}   # no milestones for stabilization


@pytest.mark.asyncio
async def test_stabilization_seed_tasks():
    crud = _make_crud()

    result = await create_stabilization_project(
        crud=crud,
        project_id="proj-stab-4",
        subject="Broker Connectivity",
    )

    total_expected = sum(len(v) for v in _STABILIZATION_SEED_TASKS.values())
    assert len(result.task_gids) == total_expected


# ---------------------------------------------------------------------------
# Batch chunking — sections > 10
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sections_batched_in_chunks_of_10():
    """When more than 10 sections exist, batch_create_sections is called multiple times."""
    crud = _make_crud()

    # Patch _ONBOARDING_SECTIONS with a 12-section list temporarily
    many_sections = [f"Section {i}" for i in range(12)]

    with patch("sidecar.automation.templates._ONBOARDING_SECTIONS", many_sections):
        result = await create_pm_onboarding_project(
            crud=crud,
            project_id="proj-chunk-test",
            pm_name="Test",
            strategy_label="X",
        )

    # Should have been called at least twice (10 + 2)
    call_count = crud.batch_create_sections.call_count
    assert call_count >= 2


# ---------------------------------------------------------------------------
# ProjectTemplateResult defaults
# ---------------------------------------------------------------------------

def test_project_template_result_defaults():
    r = ProjectTemplateResult(project_gid="gid-1")
    assert r.section_gids == {}
    assert r.milestone_gids == {}
    assert r.task_gids == []
    assert r.project_id == ""
