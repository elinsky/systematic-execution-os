"""Project tools — list, get, milestones, update."""

from __future__ import annotations

from claude_agent_sdk import tool

from agent.tools._http import err, get, ok, patch


@tool(
    "list_projects",
    "List projects. Optional filters: pm_id, project_status "
    "(planning|active|on_hold|at_risk|complete|cancelled), health "
    "(green|yellow|red|unknown), project_type "
    "(pm_onboarding|capability_build|remediation|expansion|investigation), "
    "at_risk_only (true/false).",
    {"pm_id": str, "project_status": str, "health": str, "project_type": str,
     "at_risk_only": str},
)
async def list_projects(args: dict) -> dict:
    params = {}
    for key in ("pm_id", "project_status", "health", "project_type", "at_risk_only"):
        if args.get(key):
            params[key] = args[key]
    try:
        data = await get("/projects", params=params or None)
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "get_project",
    "Get project detail including milestones, open risks, and pending decisions. "
    "Requires project_id.",
    {"project_id": str},
)
async def get_project(args: dict) -> dict:
    project_id = args.get("project_id")
    if not project_id:
        return err("project_id is required")
    try:
        data = await get(f"/projects/{project_id}")
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "get_project_milestones",
    "List milestones for a specific project. Requires project_id.",
    {"project_id": str},
)
async def get_project_milestones(args: dict) -> dict:
    project_id = args.get("project_id")
    if not project_id:
        return err("project_id is required")
    try:
        data = await get(f"/projects/{project_id}/milestones")
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "update_project",
    "[WRITE] Update a project. CONFIRM with user before calling. "
    "Requires project_id. Optional fields: status "
    "(planning|active|on_hold|at_risk|complete|cancelled), health "
    "(green|yellow|red|unknown), priority (critical|high|medium|low), "
    "owner, target_date (YYYY-MM-DD), success_criteria.",
    {"project_id": str, "status": str, "health": str, "priority": str,
     "owner": str, "target_date": str, "success_criteria": str},
)
async def update_project(args: dict) -> dict:
    project_id = args.get("project_id")
    if not project_id:
        return err("project_id is required")
    payload = {k: v for k, v in args.items() if v is not None}
    try:
        data = await patch(f"/projects/{project_id}", payload)
        return ok(data)
    except Exception as e:
        return err(str(e))
