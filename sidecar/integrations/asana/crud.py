"""CRUD operations for each domain object type against the Asana API.

This layer composes AsanaClient (transport) + AsanaMapper (translation)
to provide high-level, domain-aware operations.

Idempotency pattern:
    Before creating any Asana object the caller should check whether
    ``asana_gid`` is already set on the sidecar record. If it is, call the
    update variant instead. ``AsanaCRUD`` does *not* manage the sidecar DB —
    that responsibility belongs to the service layer. These methods only
    talk to the Asana API and return translated domain objects.

All methods raise:
    AsanaAuthError      — on 401/403
    AsanaNotFoundError  — on 404 (caller should mark record as orphaned)
    AsanaRateLimitError — when rate limit retries exhausted
    AsanaAPIError       — for other non-retryable errors
"""

from __future__ import annotations

from datetime import date
from typing import Any, AsyncIterator

import structlog

from sidecar.models import (
    Milestone,
    MilestoneConfidence,
    MilestoneStatus,
    NeedCategory,
    PMCoverageRecord,
    PMNeed,
    Project,
    ProjectType,
    RiskBlocker,
    RiskSeverity,
    RiskType,
    BusinessImpact,
    Urgency,
)
from .client import (
    AsanaClient,
    MILESTONE_OPT_FIELDS,
    PROJECT_OPT_FIELDS,
    TASK_OPT_FIELDS,
)
from .mapper import AsanaFieldConfig, AsanaMapper

logger = structlog.get_logger(__name__)


class AsanaCRUD:
    """High-level Asana CRUD operations mapped to domain models.

    Usage::

        crud = AsanaCRUD(client, mapper)

        # Fetch a project and get a domain model back
        project = await crud.get_project(project_gid, project_id="proj-123")

        # Create a task in Asana and get a domain model back
        need = await crud.create_pm_need(
            pm_need_id="need-abc",
            pm_id="pm-jane",
            title="Jane Doe - Execution - DMA via Goldman",
            ...
        )
    """

    def __init__(self, client: AsanaClient, mapper: AsanaMapper) -> None:
        self._client = client
        self._mapper = mapper

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    async def get_project(
        self,
        project_gid: str,
        project_id: str,
    ) -> Project:
        data = await self._client.get(
            f"projects/{project_gid}",
            params={"opt_fields": PROJECT_OPT_FIELDS},
        )
        return self._mapper.from_asana_project(data, project_id)

    async def create_project(
        self,
        project_id: str,
        name: str,
        project_type: ProjectType,
        team_gid: str | None = None,
        owner_gid: str | None = None,
        start_date: date | None = None,
        target_date: date | None = None,
        notes: str | None = None,
    ) -> Project:
        body = self._mapper.to_asana_project(
            name=name,
            project_type=project_type,
            workspace_gid=self._client.workspace_gid,
            team_gid=team_gid,
            owner_gid=owner_gid,
            start_date=start_date,
            target_date=target_date,
            notes=notes,
        )
        data = await self._client.post("projects", body)
        logger.info("asana_project_created", gid=data.get("gid"), name=name)
        return self._mapper.from_asana_project(data, project_id)

    async def update_project(
        self,
        project_gid: str,
        project_id: str,
        updates: dict[str, Any],
    ) -> Project:
        """Patch an Asana project with arbitrary field updates.

        ``updates`` should contain only the fields to change, using Asana
        field names (e.g. ``{"due_on": "2026-06-01", "notes": "..."}``)
        """
        data = await self._client.patch(f"projects/{project_gid}", updates)
        logger.info("asana_project_updated", gid=project_gid)
        return self._mapper.from_asana_project(data, project_id)

    async def list_projects(
        self,
        archived: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield raw Asana project dicts for the configured workspace."""
        params = {
            "workspace": self._client.workspace_gid,
            "opt_fields": PROJECT_OPT_FIELDS,
            "archived": str(archived).lower(),
        }
        async for item in self._client.paginate("projects", params=params):
            yield item

    async def list_project_tasks(
        self,
        project_gid: str,
        completed: bool | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield raw Asana task dicts for a given project."""
        params: dict[str, Any] = {"opt_fields": TASK_OPT_FIELDS}
        if completed is not None:
            params["completed_since"] = "now" if not completed else ""
        async for item in self._client.paginate(
            f"projects/{project_gid}/tasks", params=params
        ):
            yield item

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    async def list_sections(self, project_gid: str) -> list[dict[str, Any]]:
        """Return all sections in a project."""
        sections: list[dict[str, Any]] = []
        async for s in self._client.paginate(
            f"projects/{project_gid}/sections",
            params={"opt_fields": "gid,name"},
        ):
            sections.append(s)
        return sections

    async def create_section(self, project_gid: str, name: str) -> dict[str, Any]:
        data = await self._client.post(
            f"projects/{project_gid}/sections",
            {"name": name, "project": project_gid},
        )
        logger.info("asana_section_created", project_gid=project_gid, name=name)
        return data

    async def move_task_to_section(
        self, section_gid: str, task_gid: str
    ) -> None:
        """Move a task into a section (Kanban column move)."""
        await self._client.post(
            f"sections/{section_gid}/addTask",
            {"task": task_gid},
        )

    # ------------------------------------------------------------------
    # Tasks (generic — used by PM Need and Risk)
    # ------------------------------------------------------------------

    async def get_task(self, task_gid: str) -> dict[str, Any]:
        return await self._client.get(
            f"tasks/{task_gid}",
            params={"opt_fields": TASK_OPT_FIELDS},
        )

    async def update_task(
        self, task_gid: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Patch a task with arbitrary field updates."""
        data = await self._client.patch(f"tasks/{task_gid}", updates)
        logger.info("asana_task_updated", gid=task_gid)
        return data

    async def complete_task(self, task_gid: str) -> dict[str, Any]:
        return await self.update_task(task_gid, {"completed": True})

    async def set_task_external_id(
        self, task_gid: str, external_id: str
    ) -> None:
        """Store the sidecar's internal ID in the Asana task's external.id field.

        This enables idempotent lookup: given a sidecar ID, fetch the matching
        Asana task without a DB query by searching external.id.

        Note: the external field is only available on Asana workspaces using
        app-based OAuth integrations. On PAT-only workspaces this will silently
        no-op — the sidecar falls back to DB-based lookup in that case.
        """
        try:
            await self._client.patch(
                f"tasks/{task_gid}",
                {"external": {"id": external_id}},
            )
        except Exception as exc:
            logger.warning(
                "asana_external_id_skipped",
                task_gid=task_gid,
                external_id=external_id,
                reason=str(exc),
            )

    async def add_task_dependency(
        self, task_gid: str, dependency_gid: str
    ) -> None:
        """Mark task_gid as depending on dependency_gid."""
        await self._client.post(
            f"tasks/{task_gid}/addDependencies",
            {"dependencies": [dependency_gid]},
        )

    # ------------------------------------------------------------------
    # PM Coverage
    # ------------------------------------------------------------------

    async def get_pm_coverage_task(
        self,
        task_gid: str,
        pm_id: str,
    ) -> PMCoverageRecord:
        data = await self.get_task(task_gid)
        return self._mapper.from_asana_pm_coverage(data, pm_id)

    async def create_pm_coverage_task(
        self,
        pm_id: str,
        pm_name: str,
        coverage_owner_gid: str | None,
        go_live_target_date: date | None,
    ) -> PMCoverageRecord:
        cfg = self._mapper._cfg
        if not cfg.pm_coverage_project_gid:
            raise RuntimeError(
                "pm_coverage_project_gid not set in AsanaFieldConfig. "
                "Run seed_config.py to populate GIDs."
            )
        body = self._mapper.to_asana_pm_coverage(
            pm_name=pm_name,
            coverage_owner_gid=coverage_owner_gid,
            go_live_target_date=go_live_target_date,
            project_gid=cfg.pm_coverage_project_gid,
        )
        data = await self._client.post("tasks", body)
        # Store sidecar ID in Asana external field for idempotent lookup
        await self.set_task_external_id(data["gid"], f"sidecar:pm:{pm_id}")
        logger.info("asana_pm_coverage_created", gid=data["gid"], pm_id=pm_id)
        return self._mapper.from_asana_pm_coverage(data, pm_id)

    # ------------------------------------------------------------------
    # PM Needs
    # ------------------------------------------------------------------

    async def get_pm_need_task(
        self,
        task_gid: str,
        pm_need_id: str,
        pm_id: str,
    ) -> PMNeed:
        data = await self.get_task(task_gid)
        return self._mapper.from_asana_pm_need(data, pm_need_id, pm_id)

    async def create_pm_need_task(
        self,
        pm_need_id: str,
        pm_id: str,
        title: str,
        category: NeedCategory,
        urgency: Urgency,
        business_impact: BusinessImpact,
        desired_by_date: date | None = None,
        notes: str | None = None,
    ) -> PMNeed:
        cfg = self._mapper._cfg
        if not cfg.pm_needs_project_gid:
            raise RuntimeError(
                "pm_needs_project_gid not set in AsanaFieldConfig."
            )
        body = self._mapper.to_asana_pm_need(
            title=title,
            category=category,
            urgency=urgency,
            business_impact=business_impact,
            desired_by_date=desired_by_date,
            project_gid=cfg.pm_needs_project_gid,
            notes=notes,
        )
        data = await self._client.post("tasks", body)
        await self.set_task_external_id(data["gid"], f"sidecar:pmneed:{pm_need_id}")
        logger.info(
            "asana_pm_need_created",
            gid=data["gid"],
            pm_need_id=pm_need_id,
            pm_id=pm_id,
        )
        return self._mapper.from_asana_pm_need(data, pm_need_id, pm_id)

    async def update_pm_need_custom_fields(
        self,
        task_gid: str,
        pm_need_id: str,
        pm_id: str,
        urgency: Urgency | None = None,
        business_impact: BusinessImpact | None = None,
        enum_option_gids: dict[str, str] | None = None,
    ) -> PMNeed:
        """Update PM Need custom fields.

        ``enum_option_gids`` must map field_gid → enum_option_gid. Asana enum
        fields require the option GID (not the option name/value string). Callers
        should look up option GIDs from ``GET /custom_fields/{gid}`` once and cache.

        If ``enum_option_gids`` is not provided, custom fields are not updated.
        """
        updates: dict[str, Any] = {}
        if enum_option_gids:
            updates["custom_fields"] = enum_option_gids

        if updates:
            data = await self.update_task(task_gid, updates)
        else:
            data = await self.get_task(task_gid)
        return self._mapper.from_asana_pm_need(data, pm_need_id, pm_id)

    # ------------------------------------------------------------------
    # Milestones
    # ------------------------------------------------------------------

    async def get_milestone(
        self,
        task_gid: str,
        milestone_id: str,
        project_id: str,
    ) -> Milestone:
        data = await self._client.get(
            f"tasks/{task_gid}",
            params={"opt_fields": MILESTONE_OPT_FIELDS},
        )
        return self._mapper.from_asana_milestone(data, milestone_id, project_id)

    async def create_milestone(
        self,
        milestone_id: str,
        project_id: str,
        name: str,
        project_gid: str,
        target_date: date | None = None,
        owner_gid: str | None = None,
        acceptance_criteria: str | None = None,
    ) -> Milestone:
        body = self._mapper.to_asana_milestone(
            name=name,
            project_gid=project_gid,
            target_date=target_date,
            owner_gid=owner_gid,
            acceptance_criteria=acceptance_criteria,
        )
        data = await self._client.post("tasks", body)
        await self.set_task_external_id(
            data["gid"], f"sidecar:milestone:{milestone_id}"
        )
        logger.info(
            "asana_milestone_created",
            gid=data["gid"],
            milestone_id=milestone_id,
            project_id=project_id,
        )
        return self._mapper.from_asana_milestone(data, milestone_id, project_id)

    async def update_milestone_confidence(
        self,
        task_gid: str,
        milestone_id: str,
        project_id: str,
        confidence: MilestoneConfidence,
    ) -> Milestone:
        cfg = self._mapper._cfg
        updates: dict[str, Any] = {}
        if cfg.milestone_confidence_gid:
            updates["custom_fields"] = {
                cfg.milestone_confidence_gid: confidence.value
            }
        data = await self.update_task(task_gid, updates)
        return self._mapper.from_asana_milestone(data, milestone_id, project_id)

    async def update_milestone_status(
        self,
        task_gid: str,
        milestone_id: str,
        project_id: str,
        status: MilestoneStatus,
        target_date: date | None = None,
    ) -> Milestone:
        cfg = self._mapper._cfg
        updates: dict[str, Any] = {}
        if cfg.milestone_status_gid:
            updates["custom_fields"] = {cfg.milestone_status_gid: status.value}
        if status == MilestoneStatus.COMPLETE:
            updates["completed"] = True
        if target_date:
            updates["due_on"] = target_date.isoformat()
        data = await self.update_task(task_gid, updates)
        return self._mapper.from_asana_milestone(data, milestone_id, project_id)

    async def list_project_milestones(
        self,
        project_gid: str,
        project_id: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield raw Asana task dicts for milestone tasks in a project."""
        params = {
            "opt_fields": MILESTONE_OPT_FIELDS,
            "resource_subtype": "milestone",
        }
        async for item in self._client.paginate(
            f"projects/{project_gid}/tasks", params=params
        ):
            # Asana doesn't filter by subtype server-side in all plans;
            # filter client-side as a safety net.
            if item.get("resource_subtype") == "milestone":
                yield item

    # ------------------------------------------------------------------
    # Risks & Blockers
    # ------------------------------------------------------------------

    async def get_risk(self, task_gid: str, risk_id: str) -> RiskBlocker:
        data = await self.get_task(task_gid)
        return self._mapper.from_asana_risk(data, risk_id)

    async def create_risk(
        self,
        risk_id: str,
        title: str,
        risk_type: RiskType,
        severity: RiskSeverity,
        owner_gid: str | None = None,
        mitigation_plan: str | None = None,
    ) -> RiskBlocker:
        cfg = self._mapper._cfg
        if not cfg.risks_project_gid:
            raise RuntimeError("risks_project_gid not set in AsanaFieldConfig.")
        body = self._mapper.to_asana_risk(
            title=title,
            risk_type=risk_type,
            severity=severity,
            project_gid=cfg.risks_project_gid,
            mitigation_plan=mitigation_plan,
            owner_gid=owner_gid,
        )
        data = await self._client.post("tasks", body)
        await self.set_task_external_id(data["gid"], f"sidecar:risk:{risk_id}")
        logger.info("asana_risk_created", gid=data["gid"], risk_id=risk_id)
        return self._mapper.from_asana_risk(data, risk_id)

    async def resolve_risk(self, task_gid: str, risk_id: str) -> RiskBlocker:
        """Mark a risk/blocker task as complete in Asana."""
        data = await self.complete_task(task_gid)
        logger.info("asana_risk_resolved", gid=task_gid, risk_id=risk_id)
        return self._mapper.from_asana_risk(data, risk_id)

    # ------------------------------------------------------------------
    # Webhooks registration
    # ------------------------------------------------------------------

    async def list_webhooks(self) -> list[dict[str, Any]]:
        """Return all webhooks registered for the workspace."""
        result: list[dict[str, Any]] = []
        async for item in self._client.paginate(
            "webhooks",
            params={
                "workspace": self._client.workspace_gid,
                "opt_fields": "gid,resource.gid,target,active",
            },
        ):
            result.append(item)
        return result

    async def create_webhook(
        self,
        resource_gid: str,
        target_url: str,
        filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Register an Asana webhook on a project or workspace resource."""
        body: dict[str, Any] = {
            "resource": resource_gid,
            "target": target_url,
        }
        if filters:
            body["filters"] = filters
        data = await self._client.post("webhooks", body)
        logger.info(
            "asana_webhook_created",
            gid=data.get("gid"),
            resource_gid=resource_gid,
            target=target_url,
        )
        return data

    async def delete_webhook(self, webhook_gid: str) -> None:
        await self._client.delete(f"webhooks/{webhook_gid}")
        logger.info("asana_webhook_deleted", gid=webhook_gid)

    # ------------------------------------------------------------------
    # Batch project template instantiation
    # ------------------------------------------------------------------

    async def batch_create_sections(
        self,
        project_gid: str,
        section_names: list[str],
    ) -> list[dict[str, Any]]:
        """Create up to 10 sections in a single batch request.

        For larger section lists, call in chunks of 10.
        Returns list of created section dicts.
        """
        ops = [
            {
                "method": "POST",
                "relative_path": f"/projects/{project_gid}/sections",
                "data": {"name": name},
            }
            for name in section_names[:10]
        ]
        results = await self._client.batch(ops)
        created = []
        for r in results:
            if r.get("status_code") in (200, 201):
                created.append(r.get("body", {}).get("data", {}))
        return created

    async def batch_create_tasks(
        self,
        task_bodies: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Create up to 10 tasks in a single batch request.

        ``task_bodies`` should be pre-built Asana task body dicts (from mapper).
        Returns list of created task dicts.
        """
        ops = [
            {"method": "POST", "relative_path": "/tasks", "data": body}
            for body in task_bodies[:10]
        ]
        results = await self._client.batch(ops)
        created = []
        for r in results:
            if r.get("status_code") in (200, 201):
                created.append(r.get("body", {}).get("data", {}))
        return created
