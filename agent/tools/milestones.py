"""Milestone tools — list, update."""

from __future__ import annotations

from claude_agent_sdk import tool

from agent.tools._http import err, get, ok, patch


@tool(
    "list_milestones",
    "List milestones. Optional filters: project_id, milestone_status "
    "(not_started|in_progress|at_risk|complete|missed|deferred), "
    "at_risk_only (true/false), due_within_days (integer).",
    {"project_id": str, "milestone_status": str, "at_risk_only": str,
     "due_within_days": str},
)
async def list_milestones(args: dict) -> dict:
    params = {}
    for key in ("project_id", "milestone_status", "at_risk_only", "due_within_days"):
        if args.get(key):
            params[key] = args[key]
    try:
        data = await get("/milestones", params=params or None)
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "update_milestone",
    "[WRITE] Update a milestone. CONFIRM with user before calling. "
    "Requires milestone_id. Optional fields: status "
    "(not_started|in_progress|at_risk|complete|missed|deferred), confidence "
    "(high|medium|low|unknown), target_date (YYYY-MM-DD), owner, "
    "acceptance_criteria, notes.",
    {"milestone_id": str, "status": str, "confidence": str,
     "target_date": str, "owner": str, "acceptance_criteria": str, "notes": str},
)
async def update_milestone(args: dict) -> dict:
    milestone_id = args.get("milestone_id")
    if not milestone_id:
        return err("milestone_id is required")
    payload = {k: v for k, v in args.items() if v is not None}
    try:
        data = await patch(f"/milestones/{milestone_id}", payload)
        return ok(data)
    except Exception as e:
        return err(str(e))
