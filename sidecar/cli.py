"""CLI management tool for the BAM Systematic Execution OS sidecar.

Provides a human-friendly command-line interface to the sidecar REST API.
Uses argparse (stdlib) and httpx (already a project dependency).

Usage:
    python3 -m sidecar.cli <command> <subcommand> [options]

Examples:
    python3 -m sidecar.cli pm list
    python3 -m sidecar.cli needs add pm-jane-doe "Market data feed" --category market_data --urgency immediate
    python3 -m sidecar.cli risks list --severity critical --open-only
    python3 -m sidecar.cli report weekly
    python3 -m sidecar.cli status
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date
from typing import Any

import httpx

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"
TIMEOUT = 10.0


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _client() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=TIMEOUT)


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Issue a GET request and return parsed JSON. Exits on error."""
    with _client() as client:
        resp = client.get(path, params=params)
    return _handle(resp)


def _post(path: str, payload: dict[str, Any]) -> Any:
    """Issue a POST request and return parsed JSON. Exits on error."""
    with _client() as client:
        resp = client.post(path, json=payload)
    return _handle(resp)


def _handle(resp: httpx.Response) -> Any:
    """Handle response: return JSON on success, print error and exit otherwise."""
    if resp.is_success:
        return resp.json()
    _print_error(resp)
    sys.exit(1)


def _print_error(resp: httpx.Response) -> None:
    """Print a formatted error message from an HTTP response."""
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    print(f"Error {resp.status_code}: {detail}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Table formatting helpers
# ---------------------------------------------------------------------------


def _table(headers: list[str], rows: list[list[str]], col_sep: str = "  ") -> str:
    """Render a simple aligned text table."""
    if not rows:
        return "(no results)"
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))
    header_line = col_sep.join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep_line = col_sep.join("-" * w for w in widths)
    body_lines = []
    for row in rows:
        body_lines.append(col_sep.join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join([header_line, sep_line, *body_lines])


def _kv(data: dict[str, Any], keys: list[str] | None = None) -> str:
    """Render a key-value detail view."""
    if keys is None:
        keys = list(data.keys())
    max_key = max(len(k) for k in keys) if keys else 0
    lines = []
    for k in keys:
        val = data.get(k, "")
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val) if val else "(none)"
        elif val is None:
            val = "-"
        lines.append(f"  {k:<{max_key}}  {val}")
    return "\n".join(lines)


def _short_id(full_id: str) -> str:
    """Return a shortened ID for display (first 8 chars)."""
    return full_id[:8] if len(full_id) > 8 else full_id


def _gen_id(prefix: str) -> str:
    """Generate a prefixed UUID for new records."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# PM Coverage commands
# ---------------------------------------------------------------------------


def cmd_pm_list(args: argparse.Namespace) -> None:
    """List all PM coverage records."""
    data = _get("/pm-coverage")
    if not data:
        print("No PM coverage records found.")
        return
    headers = ["PM ID", "Name", "Stage", "Health", "Last Touch"]
    rows = []
    for pm in data:
        rows.append(
            [
                pm.get("pm_id", ""),
                pm.get("pm_name", ""),
                pm.get("onboarding_stage", ""),
                pm.get("health_status", ""),
                pm.get("last_touchpoint_date") or "-",
            ]
        )
    print(_table(headers, rows))
    print(f"\n{len(rows)} PM(s) total")


def cmd_pm_show(args: argparse.Namespace) -> None:
    """Show detailed PM status summary."""
    data = _get(f"/pm-coverage/{args.pm_id}")
    pm = data.get("pm", {})
    print(f"=== PM: {pm.get('pm_name', '')} ({pm.get('pm_id', '')}) ===\n")
    detail_keys = [
        "pm_id",
        "pm_name",
        "team_or_pod",
        "strategy_type",
        "region",
        "coverage_owner",
        "onboarding_stage",
        "health_status",
        "go_live_target_date",
        "last_touchpoint_date",
        "notes",
    ]
    print(_kv(pm, detail_keys))

    open_needs = data.get("open_needs", [])
    if open_needs:
        print(f"\n--- Open Needs ({len(open_needs)}) ---")
        headers = ["Need ID", "Title", "Category", "Urgency", "Status"]
        rows = []
        for n in open_needs:
            rows.append(
                [
                    _short_id(n.get("pm_need_id", "")),
                    n.get("title", "")[:50],
                    n.get("category", ""),
                    n.get("urgency", ""),
                    n.get("status", ""),
                ]
            )
        print(_table(headers, rows))

    blockers = data.get("active_blockers", [])
    if blockers:
        print(f"\n--- Active Blockers ({len(blockers)}) ---")
        headers = ["Risk ID", "Title", "Severity", "Type", "Status"]
        rows = []
        for b in blockers:
            rows.append(
                [
                    _short_id(b.get("risk_id", "")),
                    b.get("title", "")[:50],
                    b.get("severity", ""),
                    b.get("risk_type", ""),
                    b.get("status", ""),
                ]
            )
        print(_table(headers, rows))

    milestones = data.get("upcoming_milestones", [])
    if milestones:
        print(f"\n--- Upcoming Milestones ({len(milestones)}) ---")
        headers = ["Title", "Target Date", "Status", "Confidence"]
        rows = []
        for m in milestones:
            rows.append(
                [
                    m.get("title", "")[:40],
                    m.get("target_date") or "-",
                    m.get("status", ""),
                    m.get("confidence", ""),
                ]
            )
        print(_table(headers, rows))


def cmd_pm_add(args: argparse.Namespace) -> None:
    """Create a new PM coverage record."""
    payload = {
        "pm_id": args.pm_id,
        "pm_name": args.name,
    }
    result = _post("/pm-coverage", payload)
    print(f"Created PM coverage record: {result['pm_id']} ({result['pm_name']})")


# ---------------------------------------------------------------------------
# Needs commands
# ---------------------------------------------------------------------------


def cmd_needs_list(args: argparse.Namespace) -> None:
    """List PM needs with optional filters."""
    params: dict[str, Any] = {}
    if args.pm:
        params["pm_id"] = args.pm
    if args.status:
        params["need_status"] = args.status
    data = _get("/pm-needs", params=params)
    if not data:
        print("No PM needs found.")
        return
    headers = ["Need ID", "PM", "Title", "Category", "Urgency", "Status"]
    rows = []
    for n in data:
        rows.append(
            [
                _short_id(n.get("pm_need_id", "")),
                n.get("pm_id", ""),
                n.get("title", "")[:40],
                n.get("category", ""),
                n.get("urgency", ""),
                n.get("status", ""),
            ]
        )
    print(_table(headers, rows))
    print(f"\n{len(rows)} need(s) total")


def cmd_needs_show(args: argparse.Namespace) -> None:
    """Show detailed PM need."""
    data = _get(f"/pm-needs/{args.need_id}")
    print(f"=== PM Need: {data.get('title', '')} ===\n")
    detail_keys = [
        "pm_need_id",
        "pm_id",
        "title",
        "problem_statement",
        "business_rationale",
        "requested_by",
        "date_raised",
        "category",
        "urgency",
        "business_impact",
        "desired_by_date",
        "status",
        "mapped_capability_id",
        "linked_project_ids",
        "resolution_path",
        "notes",
    ]
    print(_kv(data, detail_keys))


def cmd_needs_add(args: argparse.Namespace) -> None:
    """Create a new PM need."""
    need_id = _gen_id("need")
    payload = {
        "pm_need_id": need_id,
        "pm_id": args.pm_id,
        "title": args.title,
        "category": args.category,
        "urgency": args.urgency,
        "requested_by": args.pm_id,
        "date_raised": date.today().isoformat(),
    }
    result = _post("/pm-needs", payload)
    print(f"Created PM need: {result['pm_need_id']}")
    print(f"  Title:    {result['title']}")
    print(f"  PM:       {result['pm_id']}")
    print(f"  Category: {result['category']}")
    print(f"  Urgency:  {result['urgency']}")


# ---------------------------------------------------------------------------
# Risks commands
# ---------------------------------------------------------------------------


def cmd_risks_list(args: argparse.Namespace) -> None:
    """List risks and blockers."""
    params: dict[str, Any] = {}
    if args.severity:
        params["severity"] = args.severity
    if args.open_only:
        params["open_only"] = "true"
    else:
        params["open_only"] = "false"
    data = _get("/risks", params=params)
    if not data:
        print("No risks found.")
        return
    headers = ["Risk ID", "Title", "Type", "Severity", "Status", "Opened", "Age"]
    rows = []
    for r in data:
        age = ""
        if r.get("date_opened"):
            try:
                opened = date.fromisoformat(r["date_opened"])
                age = f"{(date.today() - opened).days}d"
            except ValueError:
                age = "?"
        rows.append(
            [
                _short_id(r.get("risk_id", "")),
                r.get("title", "")[:40],
                r.get("risk_type", ""),
                r.get("severity", ""),
                r.get("status", ""),
                r.get("date_opened") or "-",
                age,
            ]
        )
    print(_table(headers, rows))
    print(f"\n{len(rows)} risk(s) total")


def cmd_risks_add(args: argparse.Namespace) -> None:
    """Create a new risk/blocker."""
    risk_id = _gen_id("risk")
    payload = {
        "risk_id": risk_id,
        "title": args.title,
        "severity": args.severity,
        "risk_type": args.type,
        "date_opened": date.today().isoformat(),
    }
    result = _post("/risks", payload)
    print(f"Created risk: {result['risk_id']}")
    print(f"  Title:    {result['title']}")
    print(f"  Type:     {result['risk_type']}")
    print(f"  Severity: {result['severity']}")


# ---------------------------------------------------------------------------
# Decisions commands
# ---------------------------------------------------------------------------


def cmd_decisions_list(args: argparse.Namespace) -> None:
    """List decisions."""
    params: dict[str, Any] = {}
    if args.pending_only:
        params["pending_only"] = "true"
    data = _get("/decisions", params=params)
    if not data:
        print("No decisions found.")
        return
    headers = ["Decision ID", "Title", "Status", "Date", "Chosen Path"]
    rows = []
    for d in data:
        rows.append(
            [
                _short_id(d.get("decision_id", "")),
                d.get("title", "")[:40],
                d.get("status", ""),
                d.get("decision_date") or "-",
                (d.get("chosen_path") or "-")[:30],
            ]
        )
    print(_table(headers, rows))
    print(f"\n{len(rows)} decision(s) total")


def cmd_decisions_add(args: argparse.Namespace) -> None:
    """Create a new decision record (initially PENDING)."""
    decision_id = _gen_id("dec")
    payload: dict[str, Any] = {
        "decision_id": decision_id,
        "title": args.title,
        "created_at": date.today().isoformat(),
    }
    if args.context:
        payload["context"] = args.context
    result = _post("/decisions", payload)
    print(f"Created decision: {result['decision_id']}")
    print(f"  Title:  {result['title']}")
    print(f"  Status: {result['status']}")


def cmd_decisions_resolve(args: argparse.Namespace) -> None:
    """Resolve a pending decision."""
    payload = {
        "decision_id": args.id,
        "chosen_path": args.path,
        "rationale": args.rationale,
        "approvers": [],
        "decision_date": date.today().isoformat(),
    }
    result = _post(f"/decisions/{args.id}/resolve", payload)
    print(f"Decision resolved: {result['decision_id']}")
    print(f"  Title:       {result['title']}")
    print(f"  Chosen path: {result['chosen_path']}")
    print(f"  Status:      {result['status']}")


# ---------------------------------------------------------------------------
# Report commands
# ---------------------------------------------------------------------------


def cmd_report_weekly(args: argparse.Namespace) -> None:
    """Generate weekly operating review agenda."""
    data = _get("/operating-review/agenda")
    print(f"=== Weekly Operating Review Agenda ({data.get('generated_on', '')}) ===\n")

    # PMs at risk
    pms = data.get("pms_at_risk", [])
    print(f"--- PMs at Risk ({len(pms)}) ---")
    if pms:
        headers = ["PM", "Health", "Reasons", "Blockers", "Open Needs"]
        rows = []
        for p in pms:
            pm = p.get("pm", {})
            rows.append(
                [
                    pm.get("pm_name", ""),
                    pm.get("health_status", ""),
                    ", ".join(p.get("reasons", [])),
                    str(len(p.get("open_blockers", []))),
                    str(p.get("open_need_count", 0)),
                ]
            )
        print(_table(headers, rows))
    else:
        print("  (none)")

    # Slipping milestones
    milestones = data.get("slipping_milestones", [])
    print(f"\n--- Slipping Milestones ({len(milestones)}) ---")
    if milestones:
        headers = ["Title", "Target Date", "Status", "Confidence"]
        rows = []
        for m in milestones:
            rows.append(
                [
                    m.get("title", "")[:40],
                    m.get("target_date") or "-",
                    m.get("status", ""),
                    m.get("confidence", ""),
                ]
            )
        print(_table(headers, rows))
    else:
        print("  (none)")

    # Aging blockers
    blockers = data.get("aging_blockers", [])
    print(f"\n--- Aging Blockers ({len(blockers)}) ---")
    if blockers:
        headers = ["Risk ID", "Title", "Severity", "Opened"]
        rows = []
        for b in blockers:
            rows.append(
                [
                    _short_id(b.get("risk_id", "")),
                    b.get("title", "")[:40],
                    b.get("severity", ""),
                    b.get("date_opened") or "-",
                ]
            )
        print(_table(headers, rows))
    else:
        print("  (none)")

    # Pending decisions
    decisions = data.get("pending_decisions", [])
    print(f"\n--- Pending Decisions ({len(decisions)}) ---")
    if decisions:
        headers = ["Decision ID", "Title", "Created"]
        rows = []
        for d in decisions:
            rows.append(
                [
                    _short_id(d.get("decision_id", "")),
                    d.get("title", "")[:40],
                    d.get("created_at") or "-",
                ]
            )
        print(_table(headers, rows))
    else:
        print("  (none)")

    # At-risk projects
    projects = data.get("at_risk_projects", [])
    print(f"\n--- At-Risk Projects ({len(projects)}) ---")
    if projects:
        headers = ["Project ID", "Name", "Status", "Health"]
        rows = []
        for p in projects:
            rows.append(
                [
                    _short_id(p.get("project_id", "")),
                    p.get("name", "")[:40],
                    p.get("status", ""),
                    p.get("health_status", ""),
                ]
            )
        print(_table(headers, rows))
    else:
        print("  (none)")


def cmd_report_portfolio(args: argparse.Namespace) -> None:
    """Portfolio health overview."""
    print("=== Portfolio Health Report ===\n")

    # At-risk PMs
    pms = _get("/operating-review/at-risk-pms")
    print(f"--- At-Risk PMs ({len(pms)}) ---")
    if pms:
        headers = ["PM", "Health", "Reasons"]
        rows = []
        for p in pms:
            pm = p.get("pm", {})
            rows.append(
                [
                    pm.get("pm_name", ""),
                    pm.get("health_status", ""),
                    ", ".join(p.get("reasons", [])),
                ]
            )
        print(_table(headers, rows))
    else:
        print("  (none)")

    # PM needs summary
    needs_summary = _get("/operating-review/pm-needs-summary")
    print("\n--- PM Needs by Category ---")
    by_cat = needs_summary.get("by_category", {})
    if by_cat:
        headers = ["Category", "Count"]
        rows = [[cat, str(count)] for cat, count in sorted(by_cat.items(), key=lambda x: -x[1])]
        print(_table(headers, rows))
    else:
        print("  (none)")

    unmet = needs_summary.get("unmet_by_pm", [])
    if unmet:
        print("\n--- Unmet Needs by PM ---")
        headers = ["PM ID", "Open Count"]
        rows = [[item["pm_id"], str(item["open_count"])] for item in unmet]
        print(_table(headers, rows))

    # Milestone calendar
    milestones = _get("/operating-review/milestone-calendar")
    print(f"\n--- Upcoming Milestones ({len(milestones)}) ---")
    if milestones:
        headers = ["Title", "Target Date", "Status"]
        rows = []
        for m in milestones:
            rows.append(
                [
                    m.get("title", "")[:40],
                    m.get("target_date") or "-",
                    m.get("status", ""),
                ]
            )
        print(_table(headers, rows))
    else:
        print("  (none)")


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    """Health check and summary."""
    # Health check
    try:
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
            resp = client.get("/health")
        if resp.is_success:
            health = resp.json()
            print(f"Sidecar status: {health.get('status', 'unknown')}")
        else:
            print(f"Sidecar health check failed: HTTP {resp.status_code}", file=sys.stderr)
            sys.exit(1)
    except httpx.ConnectError:
        print("Error: Cannot connect to sidecar at http://localhost:8000", file=sys.stderr)
        print("Is the sidecar running?  uvicorn sidecar.main:app --reload", file=sys.stderr)
        sys.exit(1)

    # Quick counts
    print()
    try:
        pms = _get("/pm-coverage")
        print(f"  PMs tracked:      {len(pms)}")
    except SystemExit:
        print("  PMs tracked:      (error fetching)")

    try:
        needs = _get("/pm-needs")
        print(f"  PM needs:         {len(needs)}")
    except SystemExit:
        print("  PM needs:         (error fetching)")

    try:
        risks = _get("/risks", params={"open_only": "true"})
        print(f"  Open risks:       {len(risks)}")
    except SystemExit:
        print("  Open risks:       (error fetching)")

    try:
        decisions = _get("/decisions", params={"pending_only": "true"})
        print(f"  Pending decisions: {len(decisions)}")
    except SystemExit:
        print("  Pending decisions: (error fetching)")


# ---------------------------------------------------------------------------
# Argparse setup
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="sidecar",
        description="CLI management tool for the BAM Systematic Execution OS sidecar.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command group")

    # ── pm ──────────────────────────────────────────────────────────────
    pm_parser = subparsers.add_parser("pm", help="PM coverage management")
    pm_sub = pm_parser.add_subparsers(dest="subcommand", help="PM subcommand")

    pm_sub.add_parser("list", help="List all PMs with health/stage")

    pm_show = pm_sub.add_parser("show", help="Show PM details")
    pm_show.add_argument("pm_id", help="PM identifier (e.g. pm-jane-doe)")

    pm_add = pm_sub.add_parser("add", help="Create PM coverage record")
    pm_add.add_argument("pm_id", help="PM identifier (e.g. pm-jane-doe)")
    pm_add.add_argument("name", help="PM display name (e.g. 'Jane Doe')")

    # ── needs ───────────────────────────────────────────────────────────
    needs_parser = subparsers.add_parser("needs", help="PM needs management")
    needs_sub = needs_parser.add_subparsers(dest="subcommand", help="Needs subcommand")

    needs_list = needs_sub.add_parser("list", help="List PM needs")
    needs_list.add_argument("--pm", default=None, help="Filter by PM ID")
    needs_list.add_argument(
        "--status",
        default=None,
        choices=[
            "new",
            "triaged",
            "mapped_to_existing_capability",
            "needs_new_project",
            "in_progress",
            "blocked",
            "delivered",
            "deferred",
            "cancelled",
        ],
        help="Filter by need status",
    )

    needs_show = needs_sub.add_parser("show", help="Show PM need details")
    needs_show.add_argument("need_id", help="PM need identifier")

    needs_add = needs_sub.add_parser("add", help="Create a new PM need")
    needs_add.add_argument("pm_id", help="PM identifier")
    needs_add.add_argument("title", help="Short title for the need")
    needs_add.add_argument(
        "--category",
        required=True,
        choices=[
            "market_data",
            "historical_data",
            "alt_data",
            "execution",
            "broker",
            "infra",
            "research",
            "ops",
            "other",
        ],
        help="Need category",
    )
    needs_add.add_argument(
        "--urgency",
        default="this_month",
        choices=["immediate", "this_week", "this_month", "next_quarter", "backlog"],
        help="Urgency level (default: this_month)",
    )

    # ── risks ───────────────────────────────────────────────────────────
    risks_parser = subparsers.add_parser("risks", help="Risk/blocker management")
    risks_sub = risks_parser.add_subparsers(dest="subcommand", help="Risks subcommand")

    risks_list = risks_sub.add_parser("list", help="List risks and blockers")
    risks_list.add_argument(
        "--severity",
        default=None,
        choices=["critical", "high", "medium", "low"],
        help="Filter by severity",
    )
    risks_list.add_argument(
        "--open-only",
        action="store_true",
        default=False,
        help="Show only open risks",
    )

    risks_add = risks_sub.add_parser("add", help="Create a new risk/blocker")
    risks_add.add_argument("title", help="Risk title")
    risks_add.add_argument(
        "--severity",
        required=True,
        choices=["critical", "high", "medium", "low"],
        help="Risk severity",
    )
    risks_add.add_argument(
        "--type",
        required=True,
        choices=["risk", "blocker", "issue"],
        help="Risk type",
    )

    # ── decisions ───────────────────────────────────────────────────────
    dec_parser = subparsers.add_parser("decisions", help="Decision log management")
    dec_sub = dec_parser.add_subparsers(dest="subcommand", help="Decisions subcommand")

    dec_list = dec_sub.add_parser("list", help="List decisions")
    dec_list.add_argument(
        "--pending-only",
        action="store_true",
        default=False,
        help="Show only pending decisions",
    )

    dec_add = dec_sub.add_parser("add", help="Create a new decision record")
    dec_add.add_argument("title", help="Decision title")
    dec_add.add_argument("--context", default=None, help="Background context for the decision")

    dec_resolve = dec_sub.add_parser("resolve", help="Resolve a pending decision")
    dec_resolve.add_argument("id", help="Decision identifier")
    dec_resolve.add_argument("--path", required=True, help="Chosen path / option selected")
    dec_resolve.add_argument("--rationale", required=True, help="Why this option was chosen")

    # ── report ──────────────────────────────────────────────────────────
    report_parser = subparsers.add_parser("report", help="Generate reports")
    report_sub = report_parser.add_subparsers(dest="subcommand", help="Report type")

    report_sub.add_parser("weekly", help="Weekly operating review agenda")
    report_sub.add_parser("portfolio", help="Portfolio health overview")

    # ── status ──────────────────────────────────────────────────────────
    subparsers.add_parser("status", help="Health check + summary")

    return parser


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

DISPATCH: dict[tuple[str, str | None], Any] = {
    ("pm", "list"): cmd_pm_list,
    ("pm", "show"): cmd_pm_show,
    ("pm", "add"): cmd_pm_add,
    ("needs", "list"): cmd_needs_list,
    ("needs", "show"): cmd_needs_show,
    ("needs", "add"): cmd_needs_add,
    ("risks", "list"): cmd_risks_list,
    ("risks", "add"): cmd_risks_add,
    ("decisions", "list"): cmd_decisions_list,
    ("decisions", "add"): cmd_decisions_add,
    ("decisions", "resolve"): cmd_decisions_resolve,
    ("report", "weekly"): cmd_report_weekly,
    ("report", "portfolio"): cmd_report_portfolio,
    ("status", None): cmd_status,
}


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and dispatch to the appropriate command handler."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    key = (args.command, getattr(args, "subcommand", None))
    handler = DISPATCH.get(key)

    if handler is None:
        # Command exists but no subcommand given — print subparser help
        sub = parser._subparsers._actions  # noqa: SLF001
        for action in sub:
            if isinstance(action, argparse._SubParsersAction):
                choice = action.choices.get(args.command)
                if choice:
                    choice.print_help()
                    break
        sys.exit(1)

    handler(args)


if __name__ == "__main__":
    main()
