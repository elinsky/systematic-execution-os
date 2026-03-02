"""PM coverage tools — list, get, create, update."""

from __future__ import annotations

from claude_agent_sdk import tool

from agent.tools._http import err, get, ok, patch, post


@tool(
    "list_pm_coverage",
    "List all PM coverage records. Optionally filter by onboarding stage "
    "(pipeline|pre_start|requirements_discovery|onboarding_in_progress|uat|"
    "go_live_ready|live|stabilization|steady_state) or health status "
    "(green|yellow|red|unknown).",
    {"stage": str, "health": str},
)
async def list_pm_coverage(args: dict) -> dict:
    params = {}
    if args.get("stage"):
        params["stage"] = args["stage"]
    if args.get("health"):
        params["health"] = args["health"]
    try:
        data = await get("/pm-coverage", params=params or None)
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "get_pm_coverage",
    "Get detailed PM status summary including open needs, active blockers, "
    "and upcoming milestones. Requires pm_id (e.g. 'pm-jane-doe').",
    {"pm_id": str},
)
async def get_pm_coverage(args: dict) -> dict:
    pm_id = args.get("pm_id")
    if not pm_id:
        return err("pm_id is required")
    try:
        data = await get(f"/pm-coverage/{pm_id}")
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "create_pm_coverage",
    "[WRITE] Create a new PM coverage record. CONFIRM with user before calling. "
    "Requires pm_id (e.g. 'pm-jane-doe') and pm_name (e.g. 'Jane Doe'). "
    "Optional: team_or_pod, strategy_type, region, coverage_owner, "
    "onboarding_stage, go_live_target_date (YYYY-MM-DD), health_status, notes.",
    {
        "pm_id": str,
        "pm_name": str,
        "team_or_pod": str,
        "strategy_type": str,
        "region": str,
        "coverage_owner": str,
        "onboarding_stage": str,
        "go_live_target_date": str,
        "health_status": str,
        "notes": str,
    },
)
async def create_pm_coverage(args: dict) -> dict:
    payload = {k: v for k, v in args.items() if v is not None}
    if "pm_id" not in payload or "pm_name" not in payload:
        return err("pm_id and pm_name are required")
    try:
        data = await post("/pm-coverage", payload)
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "update_pm_coverage",
    "[WRITE] Update a PM coverage record. CONFIRM with user before calling. "
    "Requires pm_id. Optional fields to update: onboarding_stage, health_status, "
    "go_live_target_date (YYYY-MM-DD), coverage_owner, last_touchpoint_date "
    "(YYYY-MM-DD), notes.",
    {
        "pm_id": str,
        "onboarding_stage": str,
        "health_status": str,
        "go_live_target_date": str,
        "coverage_owner": str,
        "last_touchpoint_date": str,
        "notes": str,
    },
)
async def update_pm_coverage(args: dict) -> dict:
    pm_id = args.get("pm_id")
    if not pm_id:
        return err("pm_id is required")
    payload = {k: v for k, v in args.items() if v is not None}
    try:
        data = await patch(f"/pm-coverage/{pm_id}", payload)
        return ok(data)
    except Exception as e:
        return err(str(e))
