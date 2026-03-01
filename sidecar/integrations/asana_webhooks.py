"""FastAPI-level Asana webhook bridge.

Wires the AsanaWebhookHandler (from integrations/asana/webhooks.py) to
the sidecar's pull sync logic. Registers typed event handlers that pull
the affected Asana object and upsert it into the sidecar DB.

Architecture (D4):
    Processing is synchronous within the 10-second Asana window.
    The hourly incremental poll (asana_sync.py) closes any reliability gap.

Handler registration:
    task.changed → _handle_task_changed
    task.added   → _handle_task_added (for PM Needs, Risks created via Asana)
    task.removed → _handle_task_removed (mark orphaned)

Usage:
    In main.py lifespan, call build_webhook_handler() once and mount it.
    The FastAPI route at POST /sync/webhook delegates to handler.handle().
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from sidecar.integrations.asana.client import AsanaClient, AsanaNotFoundError, TASK_OPT_FIELDS
from sidecar.integrations.asana.mapper import AsanaFieldConfig
from sidecar.integrations.asana.webhooks import AsanaWebhookHandler
from sidecar.integrations.asana_sync import (
    find_milestone_by_gid,
    find_pm_need_by_gid,
    find_risk_by_gid,
    pull_sync_milestone,
    pull_sync_pm_need_task,
    pull_sync_risk,
)

logger = structlog.get_logger(__name__)


def build_webhook_handler(
    secret: str,
    client: AsanaClient,
    field_cfg: AsanaFieldConfig,
    session_factory: Any,  # async_sessionmaker[AsyncSession]
) -> AsanaWebhookHandler:
    """Build and return a configured AsanaWebhookHandler.

    The returned handler has all event handlers registered and is ready to
    be called from the FastAPI webhook route.

    Args:
        secret:          Asana webhook secret (from settings.asana_webhook_secret).
        client:          Authenticated AsanaClient instance.
        field_cfg:       Custom field GID config (from settings).
        session_factory: SQLAlchemy async_sessionmaker for DB access.
    """
    handler = AsanaWebhookHandler(secret)

    async def _handle_task_changed(event: dict[str, Any]) -> dict[str, Any]:
        return await _sync_task_from_event(event, client, field_cfg, session_factory)

    async def _handle_task_added(event: dict[str, Any]) -> dict[str, Any]:
        return await _sync_task_from_event(event, client, field_cfg, session_factory)

    async def _handle_task_completed(event: dict[str, Any]) -> dict[str, Any]:
        return await _sync_task_from_event(event, client, field_cfg, session_factory)

    handler.register("task", "changed", _handle_task_changed)
    handler.register("task", "added", _handle_task_added)
    handler.register("task", "removed", _handle_task_completed)

    logger.info("webhook_handler_built", handlers_registered=3)
    return handler


async def _sync_task_from_event(
    event: dict[str, Any],
    client: AsanaClient,
    field_cfg: AsanaFieldConfig,
    session_factory: Any,
) -> dict[str, Any]:
    """Fetch the task from Asana and upsert the relevant sidecar record.

    Determines which sidecar entity type the task belongs to by checking
    which project it lives in (via memberships) against known singleton GIDs.
    """
    resource = event.get("resource") or {}
    task_gid = resource.get("gid", "")

    if not task_gid:
        return {"processed": False, "reason": "no_task_gid"}

    # Fetch the full task from Asana
    try:
        task = await client.get(
            f"tasks/{task_gid}",
            params={"opt_fields": TASK_OPT_FIELDS},
        )
    except AsanaNotFoundError:
        logger.warning("webhook_task_not_found", task_gid=task_gid)
        return {"processed": False, "reason": "task_deleted_in_asana"}

    # Determine which project this task belongs to
    project_gid = _first_project_gid(task)
    if not project_gid:
        return {"processed": False, "reason": "no_project_membership"}

    entity_type = _classify_task(task_gid, project_gid, task, field_cfg)

    async with session_factory() as session:
        try:
            result = await _upsert_entity(
                entity_type, task, task_gid, field_cfg, session
            )
            await session.commit()
            return result
        except Exception as exc:
            await session.rollback()
            logger.error(
                "webhook_sync_error",
                task_gid=task_gid,
                entity_type=entity_type,
                error=str(exc),
            )
            return {"processed": False, "reason": "db_error", "error": str(exc)}


def _first_project_gid(task: dict[str, Any]) -> str | None:
    for m in task.get("memberships") or []:
        gid = (m.get("project") or {}).get("gid")
        if gid:
            return gid
    return None


def _classify_task(
    task_gid: str,
    project_gid: str,
    task: dict[str, Any],
    field_cfg: AsanaFieldConfig,
) -> str:
    """Return entity type string based on project membership."""
    if project_gid == field_cfg.pm_needs_project_gid:
        return "pm_need"
    if project_gid == field_cfg.risks_project_gid:
        return "risk"
    # Milestone tasks can live in any onboarding/capability project
    if task.get("resource_subtype") == "milestone":
        return "milestone"
    return "deliverable"  # standard task — we track existence but don't replicate


async def _upsert_entity(
    entity_type: str,
    task: dict[str, Any],
    task_gid: str,
    field_cfg: AsanaFieldConfig,
    session: AsyncSession,
) -> dict[str, Any]:
    """Route to the appropriate pull sync function based on entity type."""

    if entity_type == "pm_need":
        existing = await find_pm_need_by_gid(session, task_gid)
        if existing:
            pm_need_id = existing.need_id
            pm_id = existing.pm_id
        else:
            # New PM Need created directly in Asana (e.g. via form)
            pm_need_id = f"pmneed-{task_gid}"
            pm_id = "unknown"  # service layer should reconcile pm_id
        await pull_sync_pm_need_task(session, task, pm_need_id, pm_id, field_cfg)
        return {"processed": True, "entity_type": "pm_need", "gid": task_gid}

    if entity_type == "risk":
        existing = await find_risk_by_gid(session, task_gid)
        risk_id = existing.risk_id if existing else f"risk-{task_gid}"
        await pull_sync_risk(session, task, risk_id, field_cfg)
        return {"processed": True, "entity_type": "risk", "gid": task_gid}

    if entity_type == "milestone":
        existing = await find_milestone_by_gid(session, task_gid)
        if existing:
            milestone_id = existing.milestone_id
            project_id = existing.project_id
        else:
            milestone_id = f"ms-{task_gid}"
            # Infer project_id from the task's first project membership
            project_gid = _first_project_gid(task) or ""
            project_id = f"proj-{project_gid}"
        await pull_sync_milestone(session, task, milestone_id, project_id, field_cfg)
        return {"processed": True, "entity_type": "milestone", "gid": task_gid}

    # deliverable — log but don't replicate
    logger.debug("webhook_deliverable_skipped", task_gid=task_gid)
    return {"processed": False, "entity_type": "deliverable", "reason": "not_replicated"}
