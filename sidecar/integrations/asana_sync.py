"""Sync logic between Asana and the sidecar database.

Pull sync (Asana → sidecar):
    Page through Asana API results for a given project/entity type,
    upsert each record into SQLite using asana_gid as the idempotency key.
    Sidecar-only fields (notes, linked_project_ids, etc.) are preserved on update.

Push sync (sidecar → Asana):
    Called after sidecar creates a record that needs an Asana counterpart.
    Writes the Asana GID back onto the sidecar row once created.

Design decisions honored (design-decisions.md):
    D4: Synchronous processing in v1 — no async job queue needed.
    D6: Simplified sync tracking — asana_gid + asana_synced_at only.
    D7: age_days computed on read, not written back to Asana.
    D2: PM Coverage onboarding_stage / health driven by Asana section — pull only.
    D1: PM Need status driven by Asana section — pull only.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.db.milestone import MilestoneTable
from sidecar.db.pm_coverage import PMCoverageTable
from sidecar.db.pm_need import PMNeedTable
from sidecar.db.project import ProjectTable
from sidecar.db.risk import RiskTable
from sidecar.integrations.asana.client import AsanaClient, AsanaNotFoundError, TASK_OPT_FIELDS, PROJECT_OPT_FIELDS
from sidecar.integrations.asana.mapper import AsanaFieldConfig, AsanaMapper

logger = structlog.get_logger(__name__)

_NOW = lambda: datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Pull sync helpers
# ---------------------------------------------------------------------------

def _custom_fields_index(task: dict[str, Any]) -> dict[str, Any]:
    return {cf["gid"]: cf for cf in task.get("custom_fields") or []}


def _section_name(task: dict[str, Any]) -> str:
    for m in task.get("memberships") or []:
        name = (m.get("section") or {}).get("name", "")
        if name:
            return name
    return ""


def _parse_date_str(raw: str | None) -> date | None:
    """Parse an ISO date or datetime string into a Python date object.

    SQLAlchemy's Date columns require date objects, not strings.
    """
    if not raw:
        return None
    try:
        if len(raw) == 10:
            return date.fromisoformat(raw)
        return datetime.fromisoformat(raw.rstrip("Z")).date()
    except (ValueError, AttributeError):
        return None


def _enum_val(fields: dict[str, Any], gid: str | None) -> str | None:
    if not gid or gid not in fields:
        return None
    cf = fields[gid]
    ev = cf.get("enum_value")
    if ev:
        return ev.get("name", "").lower().replace(" ", "_") or None
    return cf.get("text_value") or None


# ---------------------------------------------------------------------------
# PM Coverage pull sync
# ---------------------------------------------------------------------------

async def pull_sync_pm_coverage_task(
    session: AsyncSession,
    task: dict[str, Any],
    pm_id: str,
    field_cfg: AsanaFieldConfig,
) -> bool:
    """Upsert a PM Coverage task from Asana into the sidecar DB.

    Returns True if a new row was inserted, False if updated.
    """
    fields = _custom_fields_index(task)
    section = _section_name(task)
    now = _NOW()

    # Map section → onboarding_stage string
    mapper = AsanaMapper(field_cfg)
    stage = mapper._stage_from_section(section).value
    health_raw = _enum_val(fields, field_cfg.health_gid)
    health = health_raw if health_raw else "unknown"

    row = {
        "pm_id": pm_id,
        "pm_name": task.get("name", ""),
        "onboarding_stage": stage,
        "health_status": health,
        "region": _enum_val(fields, field_cfg.region_gid),
        "coverage_owner": (task.get("assignee") or {}).get("name"),
        "last_touchpoint_date": _parse_date_str(
            _enum_val(fields, field_cfg.last_touchpoint_gid)
        ),
        "linked_project_ids": "[]",
        "asana_gid": task["gid"],
        "asana_synced_at": now,
    }

    # Check existence before upsert — rowcount is unreliable for ON CONFLICT
    existing = await session.execute(
        select(PMCoverageTable).where(PMCoverageTable.pm_id == pm_id)
    )
    is_new = existing.scalar_one_or_none() is None

    stmt = sqlite_insert(PMCoverageTable).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["pm_id"],
        set_={
            # Only update Asana-owned fields; preserve sidecar-only fields
            "pm_name": stmt.excluded.pm_name,
            "onboarding_stage": stmt.excluded.onboarding_stage,
            "health_status": stmt.excluded.health_status,
            "region": stmt.excluded.region,
            "coverage_owner": stmt.excluded.coverage_owner,
            "asana_gid": stmt.excluded.asana_gid,
            "asana_synced_at": stmt.excluded.asana_synced_at,
        },
    )
    await session.execute(stmt)
    logger.debug(
        "pull_sync_pm_coverage",
        pm_id=pm_id,
        gid=task["gid"],
        action="insert" if is_new else "update",
    )
    return is_new


# ---------------------------------------------------------------------------
# PM Need pull sync
# ---------------------------------------------------------------------------

async def pull_sync_pm_need_task(
    session: AsyncSession,
    task: dict[str, Any],
    pm_need_id: str,
    pm_id: str,
    field_cfg: AsanaFieldConfig,
) -> bool:
    """Upsert a PM Need task from Asana into the sidecar DB."""
    fields = _custom_fields_index(task)
    section = _section_name(task)
    mapper = AsanaMapper(field_cfg)
    status = mapper._need_status_from_section(section).value
    now = _NOW()

    category_raw = _enum_val(fields, field_cfg.need_category_gid)
    urgency_raw = _enum_val(fields, field_cfg.urgency_gid)

    row = {
        "need_id": pm_need_id,
        "pm_id": pm_id,
        "title": task.get("name", ""),
        "requested_by": (task.get("assignee") or {}).get("name") or "",
        "date_raised": _parse_date_str(task.get("created_at")) or datetime.now(timezone.utc).date(),
        "category": category_raw or "other",
        "urgency": urgency_raw or "this_month",
        "status": status,
        "desired_by_date": _parse_date_str(task.get("due_on")),
        "notes": task.get("notes") or None,
        "linked_project_ids": "[]",
        "asana_gid": task["gid"],
        "asana_synced_at": now,
    }

    existing = await session.execute(
        select(PMNeedTable).where(PMNeedTable.need_id == pm_need_id)
    )
    is_new = existing.scalar_one_or_none() is None

    stmt = sqlite_insert(PMNeedTable).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["need_id"],
        set_={
            "title": stmt.excluded.title,
            "status": stmt.excluded.status,          # D1: status from Asana section only
            "category": stmt.excluded.category,
            "urgency": stmt.excluded.urgency,
            "desired_by_date": stmt.excluded.desired_by_date,
            "notes": stmt.excluded.notes,
            "asana_gid": stmt.excluded.asana_gid,
            "asana_synced_at": stmt.excluded.asana_synced_at,
        },
    )
    await session.execute(stmt)
    logger.debug(
        "pull_sync_pm_need",
        pm_need_id=pm_need_id,
        gid=task["gid"],
        action="insert" if is_new else "update",
    )
    return is_new


# ---------------------------------------------------------------------------
# Project pull sync
# ---------------------------------------------------------------------------

async def pull_sync_project(
    session: AsyncSession,
    project: dict[str, Any],
    project_id: str,
    field_cfg: AsanaFieldConfig,
) -> bool:
    """Upsert a Project from Asana into the sidecar DB."""
    fields = _custom_fields_index(project)
    mapper = AsanaMapper(field_cfg)
    current_status = project.get("current_status") or {}
    status = mapper._project_status_from_asana(current_status).value
    health = mapper._health_from_status(current_status).value
    now = _NOW()

    type_raw = _enum_val(fields, field_cfg.project_type_gid)
    priority_raw = _enum_val(fields, field_cfg.priority_gid)

    row = {
        "project_id": project_id,
        "name": project.get("name", ""),
        "project_type": type_raw or "investigation",
        "owner": (project.get("owner") or {}).get("name"),
        "status": status,
        "priority": priority_raw or "medium",
        "health_status": health,
        "start_date": _parse_date_str(project.get("start_on")),
        "target_date": _parse_date_str(project.get("due_on")),
        "linked_pm_need_ids": "[]",
        "linked_capability_ids": "[]",
        "asana_gid": project["gid"],
        "asana_synced_at": now,
    }

    existing = await session.execute(
        select(ProjectTable).where(ProjectTable.project_id == project_id)
    )
    is_new = existing.scalar_one_or_none() is None

    stmt = sqlite_insert(ProjectTable).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["project_id"],
        set_={
            "name": stmt.excluded.name,
            "status": stmt.excluded.status,
            "health_status": stmt.excluded.health_status,
            "owner": stmt.excluded.owner,
            "target_date": stmt.excluded.target_date,
            "asana_gid": stmt.excluded.asana_gid,
            "asana_synced_at": stmt.excluded.asana_synced_at,
        },
    )
    await session.execute(stmt)
    logger.debug(
        "pull_sync_project",
        project_id=project_id,
        gid=project["gid"],
        action="insert" if is_new else "update",
    )
    return is_new


# ---------------------------------------------------------------------------
# Milestone pull sync
# ---------------------------------------------------------------------------

async def pull_sync_milestone(
    session: AsyncSession,
    task: dict[str, Any],
    milestone_id: str,
    project_id: str,
    field_cfg: AsanaFieldConfig,
) -> bool:
    """Upsert a Milestone task from Asana into the sidecar DB."""
    fields = _custom_fields_index(task)
    mapper = AsanaMapper(field_cfg)
    completed = task.get("completed", False)
    status = mapper._milestone_status(fields, completed).value
    now = _NOW()

    conf_raw = _enum_val(fields, field_cfg.milestone_confidence_gid)

    row = {
        "milestone_id": milestone_id,
        "project_id": project_id,
        "name": task.get("name", ""),
        "target_date": _parse_date_str(task.get("due_on")),
        "owner": (task.get("assignee") or {}).get("name"),
        "status": status,
        "confidence": conf_raw or "unknown",
        "acceptance_criteria": task.get("notes") or None,
        "asana_gid": task["gid"],
        "asana_synced_at": now,
    }

    existing = await session.execute(
        select(MilestoneTable).where(MilestoneTable.milestone_id == milestone_id)
    )
    is_new = existing.scalar_one_or_none() is None

    stmt = sqlite_insert(MilestoneTable).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["milestone_id"],
        set_={
            "name": stmt.excluded.name,
            "status": stmt.excluded.status,
            "confidence": stmt.excluded.confidence,
            "target_date": stmt.excluded.target_date,
            "owner": stmt.excluded.owner,
            "acceptance_criteria": stmt.excluded.acceptance_criteria,
            "asana_gid": stmt.excluded.asana_gid,
            "asana_synced_at": stmt.excluded.asana_synced_at,
        },
    )
    await session.execute(stmt)
    logger.debug(
        "pull_sync_milestone",
        milestone_id=milestone_id,
        gid=task["gid"],
        action="insert" if is_new else "update",
    )
    return is_new


# ---------------------------------------------------------------------------
# Risk pull sync
# ---------------------------------------------------------------------------

async def pull_sync_risk(
    session: AsyncSession,
    task: dict[str, Any],
    risk_id: str,
    field_cfg: AsanaFieldConfig,
) -> bool:
    """Upsert a Risk/Blocker task from Asana into the sidecar DB."""
    fields = _custom_fields_index(task)
    mapper = AsanaMapper(field_cfg)
    completed = task.get("completed", False)
    now = _NOW()

    type_raw = _enum_val(fields, field_cfg.risk_type_gid)
    sev_raw = _enum_val(fields, field_cfg.severity_gid)
    esc_raw = _enum_val(fields, field_cfg.escalation_status_gid)
    status = "resolved" if completed else "open"

    row = {
        "risk_id": risk_id,
        "title": task.get("name", ""),
        "risk_type": type_raw or "risk",
        "severity": sev_raw or "medium",
        "status": status,
        "escalation_status": esc_raw or "none",
        "mitigation_plan": task.get("notes") or None,
        "date_opened": _parse_date_str(task.get("created_at")) or datetime.now(timezone.utc).date(),
        "resolution_date": _parse_date_str(task.get("completed_at")) if completed else None,
        "impacted_pm_ids": "[]",
        "impacted_project_ids": "[]",
        "impacted_milestone_ids": "[]",
        "asana_gid": task["gid"],
        "asana_synced_at": now,
    }

    existing = await session.execute(
        select(RiskTable).where(RiskTable.risk_id == risk_id)
    )
    is_new = existing.scalar_one_or_none() is None

    stmt = sqlite_insert(RiskTable).values(**row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["risk_id"],
        set_={
            "title": stmt.excluded.title,
            "status": stmt.excluded.status,
            "severity": stmt.excluded.severity,
            "escalation_status": stmt.excluded.escalation_status,
            "mitigation_plan": stmt.excluded.mitigation_plan,
            "resolution_date": stmt.excluded.resolution_date,
            "asana_gid": stmt.excluded.asana_gid,
            "asana_synced_at": stmt.excluded.asana_synced_at,
        },
    )
    await session.execute(stmt)
    logger.debug(
        "pull_sync_risk",
        risk_id=risk_id,
        gid=task["gid"],
        action="insert" if is_new else "update",
    )
    return is_new


# ---------------------------------------------------------------------------
# Lookup helpers (asana_gid → sidecar row)
# ---------------------------------------------------------------------------

async def find_pm_coverage_by_gid(
    session: AsyncSession, asana_gid: str
) -> PMCoverageTable | None:
    result = await session.execute(
        select(PMCoverageTable).where(PMCoverageTable.asana_gid == asana_gid)
    )
    return result.scalar_one_or_none()


async def find_pm_need_by_gid(
    session: AsyncSession, asana_gid: str
) -> PMNeedTable | None:
    result = await session.execute(
        select(PMNeedTable).where(PMNeedTable.asana_gid == asana_gid)
    )
    return result.scalar_one_or_none()


async def find_milestone_by_gid(
    session: AsyncSession, asana_gid: str
) -> MilestoneTable | None:
    result = await session.execute(
        select(MilestoneTable).where(MilestoneTable.asana_gid == asana_gid)
    )
    return result.scalar_one_or_none()


async def find_risk_by_gid(
    session: AsyncSession, asana_gid: str
) -> RiskTable | None:
    result = await session.execute(
        select(RiskTable).where(RiskTable.asana_gid == asana_gid)
    )
    return result.scalar_one_or_none()


async def find_project_by_gid(
    session: AsyncSession, asana_gid: str
) -> ProjectTable | None:
    result = await session.execute(
        select(ProjectTable).where(ProjectTable.asana_gid == asana_gid)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Full pull sync for a single project's tasks (milestones + deliverables)
# ---------------------------------------------------------------------------

async def full_pull_sync_project_tasks(
    client: AsanaClient,
    session: AsyncSession,
    project_gid: str,
    project_id: str,
    field_cfg: AsanaFieldConfig,
) -> dict[str, int]:
    """Pull all tasks in a project from Asana and upsert into sidecar.

    Returns counts: {"milestones": N, "tasks": N, "skipped": N}.
    """
    counts = {"milestones": 0, "tasks": 0, "skipped": 0}

    async for task in client.paginate(
        f"projects/{project_gid}/tasks",
        params={"opt_fields": TASK_OPT_FIELDS},
    ):
        gid = task.get("gid", "")
        if not gid:
            counts["skipped"] += 1
            continue

        subtype = task.get("resource_subtype", "default_task")
        if subtype == "milestone":
            # Use gid as milestone_id — sidecar IDs may be set later by service layer
            milestone_id = f"ms-{gid}"
            await pull_sync_milestone(session, task, milestone_id, project_id, field_cfg)
            counts["milestones"] += 1
        else:
            counts["tasks"] += 1  # deliverables tracked in Asana, not replicated fully

    logger.info(
        "full_pull_sync_project_tasks",
        project_gid=project_gid,
        project_id=project_id,
        **counts,
    )
    return counts
