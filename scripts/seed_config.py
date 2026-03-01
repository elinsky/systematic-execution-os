"""Asana sandbox workspace setup script.

Creates all custom fields, singleton projects, and sections required by
asana-mapping.md, then prints the .env lines to paste into your .env file.

Run this ONCE against a fresh Asana workspace before starting the sidecar.

Usage:
    uv run python scripts/seed_config.py

Required environment variables (set before running):
    ASANA_PERSONAL_ACCESS_TOKEN   — Asana PAT with full workspace access
    ASANA_WORKSPACE_GID           — GID of the target workspace
    ASANA_TEAM_GID                — (optional) Team GID for project creation

After running, copy the printed .env lines into your .env file, then restart
the sidecar so the GIDs are loaded into Settings.

Idempotency: the script checks for existing objects by name before creating,
so it is safe to re-run. Existing objects are reused and their GIDs printed.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sidecar.integrations.asana.client import AsanaClient

# ---------------------------------------------------------------------------
# Custom field definitions
# ---------------------------------------------------------------------------

# Each entry: (field_name, field_type, options_list_or_None, env_var_suffix)
# field_type: "text" | "enum" | "number" | "date" | "checkbox"
_GLOBAL_CUSTOM_FIELDS = [
    ("Project Type",  "enum", ["pm_onboarding", "capability_build", "remediation", "expansion", "investigation"], "PROJECT_TYPE"),
    ("Priority",      "enum", ["critical", "high", "medium", "low"],             "PRIORITY"),
    ("Health",        "enum", ["green", "yellow", "red"],                        "HEALTH"),
    ("Confidence",    "enum", ["high", "medium", "low", "blocked"],              "CONFIDENCE"),
    ("Owner Group",   "text", None,                                              "OWNER_GROUP"),
    ("Region",        "enum", ["amer", "emea", "apac", "global"],                "REGION"),
]

_PM_COVERAGE_CUSTOM_FIELDS = [
    ("Onboarding Stage", "enum", ["pipeline", "pre_start", "requirements_discovery", "onboarding_in_progress", "uat", "go_live_ready", "live", "stabilization", "steady_state"], "ONBOARDING_STAGE"),
    ("Strategy Type",    "text", None,                                           "STRATEGY_TYPE"),
    ("Team / Pod",       "text", None,                                           "TEAM_POD"),
    ("Last Touchpoint",  "date", None,                                           "LAST_TOUCHPOINT"),
]

_PM_NEEDS_CUSTOM_FIELDS = [
    ("Need Category",   "enum", ["market_data", "historical_data", "alt_data", "execution", "broker", "infra", "research", "ops", "other"], "NEED_CATEGORY"),
    ("Urgency",         "enum", ["critical", "high", "medium", "low"],           "URGENCY"),
    ("Business Impact", "enum", ["high", "medium", "low"],                       "BUSINESS_IMPACT"),
    ("Need Status",     "enum", ["new", "triaged", "mapped_to_existing", "needs_new_project", "in_progress", "blocked", "delivered", "deferred", "cancelled"], "NEED_STATUS"),
    ("Resolution Path", "enum", ["existing_capability", "new_project", "deferred", "cancelled"], "RESOLUTION_PATH"),
    ("PM",              "text", None,                                            "PM_FIELD"),
    ("Requested By",    "text", None,                                            "REQUESTED_BY"),
    ("Linked Capability", "text", None,                                          "LINKED_CAPABILITY"),
]

_MILESTONE_CUSTOM_FIELDS = [
    ("Milestone Status", "enum", ["not_started", "in_progress", "at_risk", "complete", "missed"], "MILESTONE_STATUS"),
    ("Gate Type",        "enum", ["data_ready", "execution_ready", "uat_complete", "go_live_ready", "stabilization_complete", "custom"], "GATE_TYPE"),
]

_RISK_CUSTOM_FIELDS = [
    ("Item Type",         "enum", ["risk", "blocker", "issue"],                  "ITEM_TYPE"),
    ("Severity",          "enum", ["critical", "high", "medium", "low"],         "SEVERITY"),
    ("Escalation Status", "enum", ["none", "monitoring", "escalated", "resolved"], "ESCALATION_STATUS"),
    ("Impacted PMs",      "text", None,                                          "IMPACTED_PMS"),
    ("Impacted Projects", "text", None,                                          "IMPACTED_PROJECTS"),
    ("Resolution Date",   "date", None,                                          "RESOLUTION_DATE_FIELD"),
]

_DECISION_CUSTOM_FIELDS = [
    ("Decision Status", "enum", ["pending", "decided", "deferred", "cancelled"], "DECISION_STATUS"),
    ("Decision Date",   "date", None,                                            "DECISION_DATE"),
    ("Approver",        "text", None,                                            "APPROVER"),
    ("Impacted Scope",  "text", None,                                            "IMPACTED_SCOPE"),
]

# ---------------------------------------------------------------------------
# Singleton project definitions
# ---------------------------------------------------------------------------

_SINGLETON_PROJECTS = [
    {
        "name": "PM Coverage Board",
        "layout": "board",
        "env_key": "ASANA_PM_COVERAGE_PROJECT_GID",
        "sections": [
            "Pipeline", "Pre-Start", "Requirements Discovery",
            "Onboarding In Progress", "UAT", "Go Live Ready",
            "Live", "Stabilization", "Steady State",
        ],
        # Custom field env suffixes to attach to this project
        "custom_fields": [
            "HEALTH", "REGION", "LAST_TOUCHPOINT", "ONBOARDING_STAGE",
            "PRIORITY", "OWNER_GROUP",
        ],
    },
    {
        "name": "PM Needs - BAM Systematic",
        "layout": "list",
        "env_key": "ASANA_PM_NEEDS_PROJECT_GID",
        "sections": [
            "New", "Triaged", "Mapped to Existing Capability",
            "Needs New Project", "In Progress", "Blocked",
            "Delivered", "Deferred", "Cancelled",
        ],
        "custom_fields": [
            "NEED_CATEGORY", "URGENCY", "BUSINESS_IMPACT", "NEED_STATUS",
            "RESOLUTION_PATH", "PM_FIELD", "REQUESTED_BY", "LINKED_CAPABILITY",
            "PRIORITY",
        ],
    },
    {
        "name": "Risks & Blockers - BAM Systematic",
        "layout": "list",
        "env_key": "ASANA_RISKS_PROJECT_GID",
        "sections": [
            "Open - Critical", "Open - High", "Open - Medium",
            "Monitoring", "Resolved",
        ],
        "custom_fields": [
            "ITEM_TYPE", "SEVERITY", "ESCALATION_STATUS",
            "IMPACTED_PMS", "IMPACTED_PROJECTS", "RESOLUTION_DATE_FIELD",
        ],
    },
    {
        "name": "Decision Log - BAM Systematic",
        "layout": "list",
        "env_key": "ASANA_DECISION_LOG_PROJECT_GID",
        "sections": [
            "Pending Decisions", "Decisions Made", "Deferred", "Cancelled",
        ],
        "custom_fields": [
            "DECISION_STATUS", "DECISION_DATE", "APPROVER", "IMPACTED_SCOPE",
        ],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _find_or_create_custom_field(
    client: AsanaClient,
    workspace_gid: str,
    name: str,
    field_type: str,
    options: list[str] | None,
) -> str:
    """Return GID of custom field with this name, creating if absent."""
    # List existing custom fields
    async for field in client.paginate(
        f"workspaces/{workspace_gid}/custom_fields",
        params={"opt_fields": "gid,name,resource_subtype"},
    ):
        if field.get("name") == name:
            print(f"  [reuse] custom field '{name}' → {field['gid']}")
            return field["gid"]

    # Build create body (workspace is in the URL path, not the body)
    body: dict = {
        "name": name,
        "resource_subtype": field_type,
    }
    if field_type == "enum" and options:
        body["enum_options"] = [{"name": opt, "enabled": True} for opt in options]
    if field_type == "date":
        body["resource_subtype"] = "date"
    if field_type == "checkbox":
        body["resource_subtype"] = "checkbox"

    result = await client.post(f"workspaces/{workspace_gid}/custom_fields", body)
    gid = result["gid"]
    print(f"  [create] custom field '{name}' → {gid}")
    return gid


async def _find_or_create_project(
    client: AsanaClient,
    workspace_gid: str,
    team_gid: str | None,
    name: str,
    layout: str,
) -> str:
    """Return GID of project with this name, creating if absent."""
    async for proj in client.paginate(
        f"workspaces/{workspace_gid}/projects",
        params={
            "opt_fields": "gid,name,archived",
            "archived": "false",
        },
    ):
        if proj.get("name") == name:
            print(f"  [reuse] project '{name}' → {proj['gid']}")
            return proj["gid"]

    body: dict = {
        "name": name,
        "workspace": workspace_gid,
        "default_view": layout,
    }
    if team_gid:
        body["team"] = team_gid

    result = await client.post("projects", body)
    gid = result["gid"]
    print(f"  [create] project '{name}' → {gid}")
    return gid


async def _ensure_custom_fields_attached(
    client: AsanaClient,
    project_gid: str,
    field_gids: list[str],
) -> None:
    """Attach custom fields to a project if not already attached.

    Asana requires fields to be attached via addCustomFieldSetting before
    tasks in the project can use them.
    """
    # Fetch current custom field settings
    existing_gids: set[str] = set()
    async for cf in client.paginate(
        f"projects/{project_gid}/custom_field_settings",
        params={"opt_fields": "custom_field.gid"},
    ):
        gid = (cf.get("custom_field") or {}).get("gid")
        if gid:
            existing_gids.add(gid)

    for field_gid in field_gids:
        if field_gid in existing_gids:
            print(f"    [reuse]  custom field {field_gid} already attached")
        else:
            try:
                await client.post(
                    f"projects/{project_gid}/addCustomFieldSetting",
                    {"custom_field": field_gid, "is_important": False},
                )
                print(f"    [attach] custom field {field_gid}")
            except Exception as e:
                print(f"    [warn]   could not attach field {field_gid}: {e}")


async def _ensure_sections(
    client: AsanaClient,
    project_gid: str,
    section_names: list[str],
) -> dict[str, str]:
    """Create any missing sections in the project. Returns {name: gid}."""
    existing: dict[str, str] = {}
    async for s in client.paginate(
        f"projects/{project_gid}/sections",
        params={"opt_fields": "gid,name"},
    ):
        existing[s["name"]] = s["gid"]

    result = dict(existing)
    for name in section_names:
        if name not in existing:
            data = await client.post(
                f"projects/{project_gid}/sections",
                {"name": name},
            )
            result[name] = data["gid"]
            print(f"    [create] section '{name}' → {data['gid']}")
        else:
            print(f"    [reuse]  section '{name}' → {existing[name]}")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    token = os.environ.get("ASANA_PERSONAL_ACCESS_TOKEN", "")
    workspace_gid = os.environ.get("ASANA_WORKSPACE_GID", "")
    team_gid = os.environ.get("ASANA_TEAM_GID") or None

    if not token or not workspace_gid:
        print("ERROR: Set ASANA_PERSONAL_ACCESS_TOKEN and ASANA_WORKSPACE_GID in your environment.")
        sys.exit(1)

    async with AsanaClient(token=token, workspace_gid=workspace_gid) as client:
        env_lines: list[str] = []

        # ── Custom fields ──────────────────────────────────────────────────
        all_field_groups = [
            ("Global", _GLOBAL_CUSTOM_FIELDS),
            ("PM Coverage", _PM_COVERAGE_CUSTOM_FIELDS),
            ("PM Needs", _PM_NEEDS_CUSTOM_FIELDS),
            ("Milestone", _MILESTONE_CUSTOM_FIELDS),
            ("Risks & Blockers", _RISK_CUSTOM_FIELDS),
            ("Decision Log", _DECISION_CUSTOM_FIELDS),
        ]

        print("\n=== Custom Fields ===")
        field_gids: dict[str, str] = {}  # env_suffix → gid
        for group_name, fields in all_field_groups:
            print(f"\n-- {group_name} --")
            for name, ftype, opts, env_suffix in fields:
                gid = await _find_or_create_custom_field(
                    client, workspace_gid, name, ftype, opts
                )
                field_gids[env_suffix] = gid
                env_lines.append(f"ASANA_CUSTOM_FIELD_{env_suffix}={gid}")

        # ── Singleton projects ─────────────────────────────────────────────
        print("\n=== Singleton Projects ===")
        for proj_def in _SINGLETON_PROJECTS:
            print(f"\n-- {proj_def['name']} --")
            proj_gid = await _find_or_create_project(
                client, workspace_gid, team_gid,
                proj_def["name"], proj_def["layout"],
            )
            env_lines.append(f"{proj_def['env_key']}={proj_gid}")
            await _ensure_sections(client, proj_gid, proj_def["sections"])
            # Attach required custom fields so tasks can use them
            field_suffixes = proj_def.get("custom_fields", [])
            if field_suffixes:
                print(f"  -- Attaching custom fields to {proj_def['name']} --")
                field_gids_to_attach = [
                    field_gids[suffix]
                    for suffix in field_suffixes
                    if suffix in field_gids
                ]
                await _ensure_custom_fields_attached(client, proj_gid, field_gids_to_attach)

        # ── Print .env lines ───────────────────────────────────────────────
        print("\n\n" + "=" * 60)
        print("Paste the following into your .env file:")
        print("=" * 60)
        for line in env_lines:
            print(line)
        print("=" * 60)
        print("\nDone. Restart the sidecar after updating .env.")


if __name__ == "__main__":
    asyncio.run(main())
