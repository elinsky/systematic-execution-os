"""Report tools — agenda, weekly status, PM dashboard, portfolio health."""

from __future__ import annotations

from claude_agent_sdk import tool

from agent.tools._http import err, get, ok


@tool(
    "get_operating_review_agenda",
    "Get the weekly operating review agenda. Includes PMs at risk, slipping "
    "milestones, aging blockers, pending decisions, and at-risk projects. "
    "No parameters required.",
    {},
)
async def get_operating_review_agenda(args: dict) -> dict:
    try:
        data = await get("/operating-review/agenda")
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "get_weekly_status_report",
    "Get the weekly status report with PM coverage stats, open needs breakdown, "
    "risk summary, milestone status, and pending decision counts. "
    "No parameters required.",
    {},
)
async def get_weekly_status_report(args: dict) -> dict:
    try:
        data = await get("/reports/weekly-status")
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "get_pm_dashboard",
    "Get a comprehensive dashboard for a specific PM, including needs, linked "
    "projects, milestones, risks, and days since last touchpoint. "
    "Requires pm_id.",
    {"pm_id": str},
)
async def get_pm_dashboard(args: dict) -> dict:
    pm_id = args.get("pm_id")
    if not pm_id:
        return err("pm_id is required")
    try:
        data = await get(f"/reports/pm/{pm_id}/dashboard")
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "get_portfolio_health",
    "Get portfolio-wide health overview: total PMs, total projects, health/status "
    "distributions, risk counts, pending decisions, overdue milestones, and "
    "upcoming go-lives. No parameters required.",
    {},
)
async def get_portfolio_health(args: dict) -> dict:
    try:
        data = await get("/reports/portfolio-health")
        return ok(data)
    except Exception as e:
        return err(str(e))
