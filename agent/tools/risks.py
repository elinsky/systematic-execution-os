"""Risk/blocker tools — list, create, update."""

from __future__ import annotations

import uuid
from datetime import date

from claude_agent_sdk import tool

from agent.tools._http import err, get, ok, patch, post


@tool(
    "list_risks",
    "List risks and blockers. Results sorted by severity (critical first). "
    "Optional filters: risk_type (risk|blocker|issue), severity "
    "(critical|high|medium|low), risk_status (open|in_mitigation|resolved|"
    "accepted|closed), pm_id, open_only (true/false — default true), "
    "older_than_days (integer).",
    {"risk_type": str, "severity": str, "risk_status": str, "pm_id": str,
     "open_only": str, "older_than_days": str},
)
async def list_risks(args: dict) -> dict:
    params = {}
    for key in ("risk_type", "severity", "risk_status", "pm_id",
                "open_only", "older_than_days"):
        if args.get(key):
            params[key] = args[key]
    try:
        data = await get("/risks", params=params or None)
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "create_risk",
    "[WRITE] Create a new risk or blocker. CONFIRM with user before calling. "
    "Requires: title, risk_type (risk|blocker|issue), severity "
    "(critical|high|medium|low). A risk_id and date_opened are auto-generated. "
    "Optional: owner, impacted_pm_ids (comma-separated), "
    "impacted_project_ids (comma-separated), mitigation_plan, notes.",
    {"title": str, "risk_type": str, "severity": str, "owner": str,
     "impacted_pm_ids": str, "impacted_project_ids": str,
     "mitigation_plan": str, "notes": str},
)
async def create_risk(args: dict) -> dict:
    for field in ("title", "risk_type", "severity"):
        if not args.get(field):
            return err(f"{field} is required")
    payload = {k: v for k, v in args.items() if v is not None}
    payload["risk_id"] = f"risk-{uuid.uuid4().hex[:8]}"
    payload["date_opened"] = date.today().isoformat()
    # Convert comma-separated IDs to lists
    for list_field in ("impacted_pm_ids", "impacted_project_ids"):
        if list_field in payload and isinstance(payload[list_field], str):
            payload[list_field] = [
                s.strip() for s in payload[list_field].split(",") if s.strip()
            ]
    try:
        data = await post("/risks", payload)
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "update_risk",
    "[WRITE] Update a risk or blocker. CONFIRM with user before calling. "
    "Requires risk_id. Optional fields: status (open|in_mitigation|resolved|"
    "accepted|closed), severity, escalation_status (none|watching|escalated|"
    "resolved), owner, mitigation_plan, resolution_date (YYYY-MM-DD), notes.",
    {"risk_id": str, "status": str, "severity": str,
     "escalation_status": str, "owner": str, "mitigation_plan": str,
     "resolution_date": str, "notes": str},
)
async def update_risk(args: dict) -> dict:
    risk_id = args.get("risk_id")
    if not risk_id:
        return err("risk_id is required")
    payload = {k: v for k, v in args.items() if v is not None}
    try:
        data = await patch(f"/risks/{risk_id}", payload)
        return ok(data)
    except Exception as e:
        return err(str(e))
