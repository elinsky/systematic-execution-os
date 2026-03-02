"""PM needs tools — list, get, create, update."""

from __future__ import annotations

import uuid

from claude_agent_sdk import tool

from agent.tools._http import err, get, ok, patch, post


@tool(
    "list_pm_needs",
    "List PM needs. Optional filters: pm_id, need_status "
    "(new|triaged|mapped_to_existing_capability|needs_new_project|in_progress|"
    "blocked|delivered|deferred|cancelled), category "
    "(market_data|historical_data|alt_data|execution|broker|infra|research|ops|other), "
    "urgency (immediate|this_week|this_month|next_quarter|backlog), "
    "unmet_only (true/false).",
    {"pm_id": str, "need_status": str, "category": str, "urgency": str, "unmet_only": str},
)
async def list_pm_needs(args: dict) -> dict:
    params = {}
    for key in ("pm_id", "need_status", "category", "urgency", "unmet_only"):
        if args.get(key):
            params[key] = args[key]
    try:
        data = await get("/pm-needs", params=params or None)
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "get_pm_need",
    "Get a specific PM need by its ID.",
    {"pm_need_id": str},
)
async def get_pm_need(args: dict) -> dict:
    pm_need_id = args.get("pm_need_id")
    if not pm_need_id:
        return err("pm_need_id is required")
    try:
        data = await get(f"/pm-needs/{pm_need_id}")
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "create_pm_need",
    "[WRITE] Create a new PM need. CONFIRM with user before calling. "
    "Requires: pm_id, title, category "
    "(market_data|historical_data|alt_data|execution|broker|infra|research|ops|other), "
    "requested_by. A pm_need_id and date_raised will be auto-generated. "
    "Optional: urgency (immediate|this_week|this_month|next_quarter|backlog), "
    "business_impact (blocker|high|medium|low), problem_statement, "
    "business_rationale, desired_by_date (YYYY-MM-DD), notes.",
    {
        "pm_id": str,
        "title": str,
        "category": str,
        "requested_by": str,
        "urgency": str,
        "business_impact": str,
        "problem_statement": str,
        "business_rationale": str,
        "desired_by_date": str,
        "notes": str,
    },
)
async def create_pm_need(args: dict) -> dict:
    for field in ("pm_id", "title", "category", "requested_by"):
        if not args.get(field):
            return err(f"{field} is required")
    from datetime import date

    payload = {k: v for k, v in args.items() if v is not None}
    payload["pm_need_id"] = f"need-{uuid.uuid4().hex[:8]}"
    payload["date_raised"] = date.today().isoformat()
    try:
        data = await post("/pm-needs", payload)
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "update_pm_need",
    "[WRITE] Update a PM need. CONFIRM with user before calling. "
    "Requires pm_need_id. Note: status is NOT writable — it is driven by Asana. "
    "Optional fields: urgency, business_impact, mapped_capability_id, "
    "linked_project_ids (comma-separated), resolution_path, notes.",
    {
        "pm_need_id": str,
        "urgency": str,
        "business_impact": str,
        "mapped_capability_id": str,
        "linked_project_ids": str,
        "resolution_path": str,
        "notes": str,
    },
)
async def update_pm_need(args: dict) -> dict:
    pm_need_id = args.get("pm_need_id")
    if not pm_need_id:
        return err("pm_need_id is required")
    payload = {k: v for k, v in args.items() if v is not None}
    # Convert comma-separated project IDs to list
    if "linked_project_ids" in payload and isinstance(payload["linked_project_ids"], str):
        payload["linked_project_ids"] = [
            s.strip() for s in payload["linked_project_ids"].split(",") if s.strip()
        ]
    try:
        data = await patch(f"/pm-needs/{pm_need_id}", payload)
        return ok(data)
    except Exception as e:
        return err(str(e))
