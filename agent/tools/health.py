"""Health check tool."""

from __future__ import annotations

from claude_agent_sdk import tool

from agent.tools._http import err, health_get, ok


@tool(
    "check_health",
    "Check if the sidecar API is running and responsive. Returns status. "
    "No parameters required.",
    {},
)
async def check_health(args: dict) -> dict:
    try:
        data = await health_get("/health")
        return ok(data)
    except Exception as e:
        return err(f"Sidecar is not reachable: {e}")
