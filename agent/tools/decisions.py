"""Decision tools — list, create, resolve."""

from __future__ import annotations

import uuid
from datetime import date

from claude_agent_sdk import tool

from agent.tools._http import err, get, ok, post


@tool(
    "list_decisions",
    "List decisions. Optional filters: decision_status "
    "(pending|decided|superseded|deferred), project_id, "
    "pending_only (true/false), older_than_days (integer).",
    {"decision_status": str, "project_id": str, "pending_only": str, "older_than_days": str},
)
async def list_decisions(args: dict) -> dict:
    params = {}
    for key in ("decision_status", "project_id", "pending_only", "older_than_days"):
        if args.get(key):
            params[key] = args[key]
    try:
        data = await get("/decisions", params=params or None)
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "create_decision",
    "[WRITE] Create a new decision record (status: pending). CONFIRM with user "
    "before calling. Requires: title. A decision_id is auto-generated. "
    "Optional: context, options_considered, notes.",
    {"title": str, "context": str, "options_considered": str, "notes": str},
)
async def create_decision(args: dict) -> dict:
    if not args.get("title"):
        return err("title is required")
    payload = {k: v for k, v in args.items() if v is not None}
    payload["decision_id"] = f"dec-{uuid.uuid4().hex[:8]}"
    payload["created_at"] = date.today().isoformat()
    try:
        data = await post("/decisions", payload)
        return ok(data)
    except Exception as e:
        return err(str(e))


@tool(
    "resolve_decision",
    "[WRITE] Resolve a pending decision. CONFIRM with user before calling. "
    "Decisions are IMMUTABLE once decided — resolving an already-decided decision "
    "will fail with 409. Requires: decision_id, chosen_path, rationale. "
    "Optional: approvers (comma-separated names), decision_date (YYYY-MM-DD, "
    "defaults to today).",
    {
        "decision_id": str,
        "chosen_path": str,
        "rationale": str,
        "approvers": str,
        "decision_date": str,
    },
)
async def resolve_decision(args: dict) -> dict:
    for field in ("decision_id", "chosen_path", "rationale"):
        if not args.get(field):
            return err(f"{field} is required")
    decision_id = args["decision_id"]
    approvers_raw = args.get("approvers", "")
    approvers = [s.strip() for s in approvers_raw.split(",") if s.strip()] if approvers_raw else []
    payload = {
        "decision_id": decision_id,
        "chosen_path": args["chosen_path"],
        "rationale": args["rationale"],
        "approvers": approvers,
        "decision_date": args.get("decision_date") or date.today().isoformat(),
    }
    try:
        data = await post(f"/decisions/{decision_id}/resolve", payload)
        return ok(data)
    except Exception as e:
        return err(str(e))
