"""Template-based project creation for the BAM Systematic Execution OS.

Provides functions to instantiate standardized Asana projects from templates
defined in asana-mapping.md. Each template function:

1. Creates the Asana project
2. Creates sections (Kanban columns or phase buckets) in batch
3. Creates seed milestone tasks in batch
4. Creates seed regular tasks in batch
5. Returns a ProjectTemplateResult with all created GIDs

Template definitions correspond to:
    - PM Onboarding project  (10 milestones, 8 sections, ~30 tasks)
    - Capability Build project
    - Stabilization project

Usage::

    result = await create_pm_onboarding_project(
        crud=crud,
        pm_name="Jane Doe",
        strategy_label="US Equities",
        go_live_date=date(2026, 6, 1),
        team_gid="team-xyz",
    )
    # result.project_gid, result.milestone_gids, result.section_gids
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import structlog

from sidecar.integrations.asana.crud import AsanaCRUD
from sidecar.models import ProjectType
from sidecar.models.milestone import STANDARD_ONBOARDING_MILESTONES

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProjectTemplateResult:
    """GIDs of all objects created during template instantiation."""
    project_gid: str
    section_gids: dict[str, str] = field(default_factory=dict)   # name → gid
    milestone_gids: dict[str, str] = field(default_factory=dict) # name → gid
    task_gids: list[str] = field(default_factory=list)
    project_id: str = ""  # sidecar internal ID


# ---------------------------------------------------------------------------
# PM Onboarding Template
# ---------------------------------------------------------------------------

_ONBOARDING_SECTIONS = [
    "Kickoff & Discovery",
    "Requirements & Scoping",
    "Market Data & Infrastructure",
    "Execution & Connectivity",
    "UAT & Validation",
    "Go Live Readiness",
    "Post Go Live Stabilization",
    "Admin & Wrap-Up",
]

# Maps milestone name → section it belongs to
_ONBOARDING_MILESTONE_SECTIONS: dict[str, str] = {
    "Kickoff": "Kickoff & Discovery",
    "Requirements Confirmed": "Requirements & Scoping",
    "Market Data Ready": "Market Data & Infrastructure",
    "Historical Data Ready": "Market Data & Infrastructure",
    "Alt Data Ready": "Market Data & Infrastructure",
    "Execution Ready": "Execution & Connectivity",
    "UAT Complete": "UAT & Validation",
    "Go-Live Ready": "Go Live Readiness",
    "PM Live": "Go Live Readiness",
    "Stabilization Complete": "Post Go Live Stabilization",
}

_ONBOARDING_SEED_TASKS: dict[str, list[str]] = {
    "Kickoff & Discovery": [
        "Schedule kickoff meeting with PM",
        "Capture PM background and strategy overview",
        "Document initial PM needs list",
        "Identify key contacts (PM team, tech, ops, broker)",
    ],
    "Requirements & Scoping": [
        "Conduct requirements discovery sessions",
        "Document full PM needs in PM Needs project",
        "Map needs to existing capabilities or new projects",
        "Define success criteria for go-live",
        "Get PM sign-off on requirements scope",
    ],
    "Market Data & Infrastructure": [
        "Confirm market data coverage requirements",
        "Confirm historical data requirements",
        "Submit data feed requests to tech",
        "Validate data feed delivery",
    ],
    "Execution & Connectivity": [
        "Confirm broker connectivity requirements",
        "Submit DMA / broker integration requests",
        "Validate execution infrastructure",
        "End-to-end execution test",
    ],
    "UAT & Validation": [
        "Define UAT plan and criteria",
        "Run UAT sessions with PM",
        "Document and resolve UAT issues",
        "Get PM sign-off on UAT completion",
    ],
    "Go Live Readiness": [
        "Final readiness checklist",
        "Confirm support coverage on go-live day",
        "Go/no-go decision meeting",
        "Execute go-live",
    ],
    "Post Go Live Stabilization": [
        "Day 1 check-in with PM",
        "Week 1 stabilization review",
        "Capture early issues and follow-up needs",
        "Stabilization closure decision",
    ],
    "Admin & Wrap-Up": [
        "Update PM Coverage Record to Steady State",
        "Document lessons learned",
    ],
}


async def create_pm_onboarding_project(
    crud: AsanaCRUD,
    project_id: str,
    pm_name: str,
    strategy_label: str,
    go_live_date: date | None = None,
    team_gid: str | None = None,
    owner_gid: str | None = None,
) -> ProjectTemplateResult:
    """Create a complete PM Onboarding project in Asana from template.

    Creates project → sections (batched) → milestones (batched) → tasks (batched).

    Args:
        crud:           AsanaCRUD instance (wraps AsanaClient + AsanaMapper).
        project_id:     Sidecar internal ID for the project.
        pm_name:        Full PM name (used in project name and milestone names).
        strategy_label: Short label, e.g. "US Equities" (used in project name).
        go_live_date:   Target go-live date; set on project and Go-Live Ready milestone.
        team_gid:       Optional Asana team GID.
        owner_gid:      Optional Asana user GID for project owner.

    Returns:
        ProjectTemplateResult with all created GIDs.
    """
    project_name = f"Onboarding - {pm_name} - {strategy_label}"
    notes = (
        f"PM Onboarding project for {pm_name}.\n"
        f"Strategy: {strategy_label}\n"
        f"Go-live target: {go_live_date.isoformat() if go_live_date else 'TBD'}"
    )

    logger.info("creating_onboarding_project", pm_name=pm_name, project_name=project_name)

    # Step 1: Create project
    project = await crud.create_project(
        project_id=project_id,
        name=project_name,
        project_type=ProjectType.PM_ONBOARDING,
        team_gid=team_gid,
        owner_gid=owner_gid,
        target_date=go_live_date,
        notes=notes,
    )
    project_gid = project.asana_gid
    assert project_gid, "Project creation must return an asana_gid"

    result = ProjectTemplateResult(project_gid=project_gid, project_id=project_id)

    # Step 2: Create sections in batches of 10
    section_gids = await _create_sections_batched(crud, project_gid, _ONBOARDING_SECTIONS)
    result.section_gids = section_gids

    # Step 3: Create milestone tasks in batches
    milestone_gids = await _create_milestones_batched(
        crud,
        project_gid=project_gid,
        pm_name=pm_name,
        go_live_date=go_live_date,
    )
    result.milestone_gids = milestone_gids

    # Step 4: Create seed tasks in batches of 10 per section
    task_gids = await _create_seed_tasks_batched(
        crud,
        project_gid=project_gid,
        seed_tasks=_ONBOARDING_SEED_TASKS,
    )
    result.task_gids = task_gids

    logger.info(
        "onboarding_project_created",
        project_gid=project_gid,
        pm_name=pm_name,
        sections=len(section_gids),
        milestones=len(milestone_gids),
        tasks=len(task_gids),
    )
    return result


# ---------------------------------------------------------------------------
# Capability Build Template
# ---------------------------------------------------------------------------

_CAPABILITY_SECTIONS = [
    "Definition & Scoping",
    "Design & Architecture",
    "Build",
    "Testing & Validation",
    "Launch & Documentation",
    "Monitoring & Optimization",
]

_CAPABILITY_MILESTONES = [
    "Capability Definition Confirmed",
    "Architecture Approved",
    "Build Complete",
    "Testing Complete",
    "Capability Available",
    "Stable & Monitored",
]

_CAPABILITY_SEED_TASKS: dict[str, list[str]] = {
    "Definition & Scoping": [
        "Aggregate PM needs that this capability addresses",
        "Define capability scope and non-scope",
        "Identify dependent PMs and onboarding timeline",
        "Document success criteria",
        "Get business sign-off on scope",
    ],
    "Design & Architecture": [
        "Tech design review",
        "Identify dependencies on other capabilities",
        "Risk review",
        "Architecture approval",
    ],
    "Build": [
        "Sprint planning with tech team",
        "Weekly build check-ins",
    ],
    "Testing & Validation": [
        "Define test plan",
        "Conduct testing with PM(s)",
        "Resolve issues",
        "Sign-off on testing",
    ],
    "Launch & Documentation": [
        "Update Capability Registry maturity to Available",
        "Publish runbook / documentation",
        "Notify dependent PMs",
    ],
    "Monitoring & Optimization": [
        "30-day post-launch review",
        "Capture issues and gaps",
        "Update Capability Registry",
    ],
}


async def create_capability_build_project(
    crud: AsanaCRUD,
    project_id: str,
    capability_name: str,
    phase_label: str = "Phase 1",
    team_gid: str | None = None,
    owner_gid: str | None = None,
    target_date: date | None = None,
) -> ProjectTemplateResult:
    """Create a Capability Build project from template."""
    project_name = f"Capability - {capability_name} - {phase_label}"

    logger.info("creating_capability_project", capability_name=capability_name)

    project = await crud.create_project(
        project_id=project_id,
        name=project_name,
        project_type=ProjectType.CAPABILITY_BUILD,
        team_gid=team_gid,
        owner_gid=owner_gid,
        target_date=target_date,
        notes=f"Capability build project for: {capability_name} ({phase_label})",
    )
    project_gid = project.asana_gid
    assert project_gid

    result = ProjectTemplateResult(project_gid=project_gid, project_id=project_id)
    result.section_gids = await _create_sections_batched(crud, project_gid, _CAPABILITY_SECTIONS)

    # Create milestones
    milestone_bodies = [
        crud._mapper.to_asana_milestone(
            name=name,
            project_gid=project_gid,
            target_date=None,
        )
        for name in _CAPABILITY_MILESTONES
    ]
    for chunk in _chunks(milestone_bodies, 10):
        created = await crud.batch_create_tasks(chunk)
        for task_data in created:
            gid = task_data.get("gid", "")
            name = task_data.get("name", "")
            if gid and name:
                result.milestone_gids[name] = gid

    result.task_gids = await _create_seed_tasks_batched(
        crud, project_gid, _CAPABILITY_SEED_TASKS
    )

    logger.info(
        "capability_project_created",
        project_gid=project_gid,
        capability_name=capability_name,
        milestones=len(result.milestone_gids),
    )
    return result


# ---------------------------------------------------------------------------
# Stabilization Template
# ---------------------------------------------------------------------------

_STABILIZATION_SECTIONS = [
    "Active Issues",
    "Monitoring & Watch",
    "Follow-On Needs",
    "Closure Criteria",
]

_STABILIZATION_SEED_TASKS: dict[str, list[str]] = {
    "Active Issues": [
        "Day 1 issues log",
        "Week 1 issues review",
    ],
    "Monitoring & Watch": [
        "Daily PM check-in (first week)",
        "Weekly health review",
        "Escalation log",
    ],
    "Follow-On Needs": [
        "Capture follow-on PM needs",
        "Prioritize follow-on work",
        "Create new PM Needs entries",
    ],
    "Closure Criteria": [
        "Verify all critical issues resolved",
        "PM confirms readiness for steady state",
        "Update PM Coverage Record to Steady State",
        "Close stabilization project",
    ],
}


async def create_stabilization_project(
    crud: AsanaCRUD,
    project_id: str,
    subject: str,  # e.g. "Jane Doe" or "Security Master"
    team_gid: str | None = None,
    owner_gid: str | None = None,
) -> ProjectTemplateResult:
    """Create a Stabilization project from template."""
    project_name = f"Stabilization - {subject} - Post Live"

    project = await crud.create_project(
        project_id=project_id,
        name=project_name,
        project_type=ProjectType.REMEDIATION,
        team_gid=team_gid,
        owner_gid=owner_gid,
        notes=f"Post-go-live stabilization for: {subject}",
    )
    project_gid = project.asana_gid
    assert project_gid

    result = ProjectTemplateResult(project_gid=project_gid, project_id=project_id)
    result.section_gids = await _create_sections_batched(
        crud, project_gid, _STABILIZATION_SECTIONS
    )
    result.task_gids = await _create_seed_tasks_batched(
        crud, project_gid, _STABILIZATION_SEED_TASKS
    )

    logger.info(
        "stabilization_project_created",
        project_gid=project_gid,
        subject=subject,
    )
    return result


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _create_sections_batched(
    crud: AsanaCRUD,
    project_gid: str,
    section_names: list[str],
) -> dict[str, str]:
    """Create sections in batches of 10. Returns {name: gid}."""
    section_gids: dict[str, str] = {}
    for chunk in _chunks(section_names, 10):
        created = await crud.batch_create_sections(project_gid, chunk)
        for s in created:
            gid = s.get("gid", "")
            name = s.get("name", "")
            if gid and name:
                section_gids[name] = gid
    return section_gids


async def _create_milestones_batched(
    crud: AsanaCRUD,
    project_gid: str,
    pm_name: str,
    go_live_date: date | None,
) -> dict[str, str]:
    """Create standard onboarding milestones. Returns {name: gid}."""
    milestone_gids: dict[str, str] = {}

    milestone_bodies = []
    for name in STANDARD_ONBOARDING_MILESTONES:
        # Set go_live_date on the critical gate milestones
        target = go_live_date if name in ("Go-Live Ready", "PM Live") else None
        full_name = f"{pm_name} - {name}"
        body = crud._mapper.to_asana_milestone(
            name=full_name,
            project_gid=project_gid,
            target_date=target,
        )
        milestone_bodies.append(body)

    for chunk in _chunks(milestone_bodies, 10):
        created = await crud.batch_create_tasks(chunk)
        for task_data in created:
            gid = task_data.get("gid", "")
            name = task_data.get("name", "")
            if gid and name:
                milestone_gids[name] = gid

    return milestone_gids


async def _create_seed_tasks_batched(
    crud: AsanaCRUD,
    project_gid: str,
    seed_tasks: dict[str, list[str]],
) -> list[str]:
    """Create all seed tasks across all sections. Returns list of created GIDs."""
    all_task_bodies: list[dict[str, Any]] = []
    for _section, task_names in seed_tasks.items():
        for task_name in task_names:
            all_task_bodies.append({
                "name": task_name,
                "projects": [project_gid],
            })

    created_gids: list[str] = []
    for chunk in _chunks(all_task_bodies, 10):
        created = await crud.batch_create_tasks(chunk)
        for task_data in created:
            gid = task_data.get("gid", "")
            if gid:
                created_gids.append(gid)

    return created_gids


def _chunks(lst: list, size: int):
    """Yield successive chunks of up to `size` items."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]
