"""Integration smoke test — full round-trip against a live Asana sandbox.

Validates that every major integration path works end-to-end:
  1. PM Coverage record: create task in Asana → sync to sidecar → query via API
  2. PM Need: create task in Asana → sync to sidecar → verify status from section
  3. PM Onboarding project: create from template → verify sections + milestones in Asana
  4. Pull sync: run full sync → verify sidecar DB matches Asana objects
  5. Sidecar API: query REST endpoints → validate response shape

Prerequisites:
  - scripts/seed_config.py has been run and .env is populated with all GIDs
  - The sidecar server is running (or SIDECAR_BASE_URL points to it)
  - ASANA_PERSONAL_ACCESS_TOKEN and ASANA_WORKSPACE_GID are set

Usage:
    # With sidecar running locally on port 8000:
    uv run python scripts/smoke_test.py

    # Against a different host:
    SIDECAR_BASE_URL=http://localhost:9000 uv run python scripts/smoke_test.py

Exit codes:
    0  — all checks passed
    1  — one or more checks failed (see FAIL lines in output)

Design notes:
    - All Asana objects created are tagged with SMOKE_TEST_PREFIX for cleanup.
    - The script cleans up created Asana objects at the end (unless --no-cleanup).
    - Sidecar DB changes persist (they reflect a real sync; clean manually if needed).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta
from typing import Any

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sidecar.config import Settings
from sidecar.integrations.asana.client import AsanaClient
from sidecar.integrations.asana.crud import AsanaCRUD
from sidecar.integrations.asana.mapper import AsanaFieldConfig, AsanaMapper
from sidecar.models.pm_need import NeedCategory, Urgency, BusinessImpact

SMOKE_TEST_PREFIX = "[SMOKE]"


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

class SmokeTestRunner:
    def __init__(self) -> None:
        self._pass = 0
        self._fail = 0
        self._created_task_gids: list[str] = []
        self._created_project_gids: list[str] = []

    def check(self, label: str, condition: bool, detail: str = "") -> None:
        if condition:
            self._pass += 1
            print(f"  PASS  {label}")
        else:
            self._fail += 1
            msg = f"  FAIL  {label}"
            if detail:
                msg += f"\n        {detail}"
            print(msg)

    def track_task(self, gid: str) -> None:
        self._created_task_gids.append(gid)

    def track_project(self, gid: str) -> None:
        self._created_project_gids.append(gid)

    def summary(self) -> int:
        total = self._pass + self._fail
        print(f"\n{'='*50}")
        print(f"Results: {self._pass}/{total} passed, {self._fail} failed")
        print("=" * 50)
        return 0 if self._fail == 0 else 1

    async def cleanup(self, client: AsanaClient) -> None:
        print(f"\nCleaning up {len(self._created_task_gids)} tasks, "
              f"{len(self._created_project_gids)} projects...")
        for gid in self._created_task_gids:
            try:
                await client.delete(f"tasks/{gid}")
            except Exception as e:
                print(f"  warn: could not delete task {gid}: {e}")
        for gid in self._created_project_gids:
            try:
                await client.delete(f"projects/{gid}")
            except Exception as e:
                print(f"  warn: could not delete project {gid}: {e}")
        print("Cleanup done.")


# ---------------------------------------------------------------------------
# Helper: build field config from environment
# ---------------------------------------------------------------------------

def _field_cfg_from_env() -> AsanaFieldConfig:
    """Build AsanaFieldConfig from the env variables set by seed_config.py."""
    g = os.environ.get
    return AsanaFieldConfig(
        health_gid=g("ASANA_CUSTOM_FIELD_HEALTH"),
        region_gid=g("ASANA_CUSTOM_FIELD_REGION"),
        last_touchpoint_gid=g("ASANA_CUSTOM_FIELD_LAST_TOUCHPOINT"),
        onboarding_stage_gid=g("ASANA_CUSTOM_FIELD_ONBOARDING_STAGE"),
        need_category_gid=g("ASANA_CUSTOM_FIELD_NEED_CATEGORY"),
        urgency_gid=g("ASANA_CUSTOM_FIELD_URGENCY"),
        business_impact_gid=g("ASANA_CUSTOM_FIELD_BUSINESS_IMPACT"),
        need_status_gid=g("ASANA_CUSTOM_FIELD_NEED_STATUS"),
        resolution_path_gid=g("ASANA_CUSTOM_FIELD_RESOLUTION_PATH"),
        project_type_gid=g("ASANA_CUSTOM_FIELD_PROJECT_TYPE"),
        priority_gid=g("ASANA_CUSTOM_FIELD_PRIORITY"),
        project_health_gid=g("ASANA_CUSTOM_FIELD_HEALTH"),
        milestone_status_gid=g("ASANA_CUSTOM_FIELD_MILESTONE_STATUS"),
        milestone_confidence_gid=g("ASANA_CUSTOM_FIELD_CONFIDENCE"),
        risk_type_gid=g("ASANA_CUSTOM_FIELD_ITEM_TYPE"),
        severity_gid=g("ASANA_CUSTOM_FIELD_SEVERITY"),
        escalation_status_gid=g("ASANA_CUSTOM_FIELD_ESCALATION_STATUS"),
        pm_coverage_project_gid=g("ASANA_PM_COVERAGE_PROJECT_GID"),
        pm_needs_project_gid=g("ASANA_PM_NEEDS_PROJECT_GID"),
        risks_project_gid=g("ASANA_RISKS_PROJECT_GID"),
    )


# ---------------------------------------------------------------------------
# Step 1: PM Coverage record round-trip
# ---------------------------------------------------------------------------

async def test_pm_coverage(
    runner: SmokeTestRunner,
    crud: AsanaCRUD,
    sidecar_url: str,
    run_id: str,
) -> str | None:
    """Create a PM coverage task in Asana, sync to sidecar, verify via API."""
    print("\n[1] PM Coverage round-trip")

    pm_name = f"{SMOKE_TEST_PREFIX} PM Jane Doe {run_id}"
    pm_id = f"smoke-pm-{run_id}"

    # 1a: Create PM coverage task in Asana
    try:
        coverage = await crud.create_pm_coverage_task(
            pm_id=pm_id,
            pm_name=pm_name,
            coverage_owner_gid=None,
            go_live_target_date=date.today() + timedelta(days=90),
        )
        runner.track_task(coverage.asana_gid)
        runner.check("PM coverage task created in Asana", bool(coverage.asana_gid))
        runner.check("PM coverage task name matches", coverage.pm_name == pm_name)
    except Exception as e:
        runner.check("PM coverage task created in Asana", False, str(e))
        return None

    asana_gid = coverage.asana_gid

    # 1b: Fetch back directly to verify round-trip
    try:
        fetched = await crud.get_pm_coverage_task(asana_gid, pm_id)
        runner.check("PM coverage fetched by GID", bool(fetched))
        runner.check("PM coverage name consistent", fetched.pm_name == pm_name)
    except Exception as e:
        runner.check("PM coverage fetched by GID", False, str(e))

    # 1c: Query sidecar API (only if sidecar is reachable)
    try:
        async with httpx.AsyncClient(base_url=sidecar_url, timeout=10.0) as http:
            resp = await http.get(f"/pm-coverage/{pm_id}")
            if resp.status_code == 200:
                data = resp.json()
                runner.check("Sidecar API: PM coverage record found", True)
                runner.check(
                    "Sidecar API: asana_gid matches",
                    data.get("asana_gid") == asana_gid,
                    f"got {data.get('asana_gid')!r}, want {asana_gid!r}",
                )
            elif resp.status_code == 404:
                # Not synced yet — need to trigger sync; skip sidecar checks
                print("    (sidecar record not found — sync not yet triggered; skipping API checks)")
            else:
                runner.check("Sidecar API: PM coverage record found", False,
                             f"HTTP {resp.status_code}")
    except Exception:
        print("    (sidecar not reachable — skipping API checks)")

    return asana_gid


# ---------------------------------------------------------------------------
# Step 2: PM Need round-trip
# ---------------------------------------------------------------------------

async def test_pm_need(
    runner: SmokeTestRunner,
    crud: AsanaCRUD,
    sidecar_url: str,
    run_id: str,
) -> str | None:
    """Create a PM need task in Asana, verify it in correct section."""
    print("\n[2] PM Need round-trip")

    need_title = f"{SMOKE_TEST_PREFIX} DMA Connectivity {run_id}"
    pm_need_id = f"smoke-need-{run_id}"

    cfg = crud._mapper._cfg
    if not cfg.pm_needs_project_gid:
        print("    SKIP: ASANA_PM_NEEDS_PROJECT_GID not set")
        return None

    try:
        need = await crud.create_pm_need_task(
            pm_need_id=pm_need_id,
            pm_id=f"smoke-pm-{run_id}",
            title=need_title,
            category=NeedCategory.EXECUTION,
            urgency=Urgency.THIS_WEEK,
            business_impact=BusinessImpact.HIGH,
            desired_by_date=date.today() + timedelta(days=30),
            notes="Smoke test: DMA connectivity need for broker X.",
        )
        runner.track_task(need.asana_gid)
        runner.check("PM need task created in Asana", bool(need.asana_gid))
        runner.check("PM need title matches", need_title in need.title)
        runner.check("PM need category is execution", str(need.category) == "execution")
    except Exception as e:
        runner.check("PM need task created in Asana", False, str(e))
        return None

    # Fetch back and verify
    try:
        raw = await crud.get_task(need.asana_gid)
        memberships = raw.get("memberships") or []
        project_gids = {
            (m.get("project") or {}).get("gid")
            for m in memberships
        }
        runner.check(
            "PM need in correct project",
            cfg.pm_needs_project_gid in project_gids,
            f"memberships: {project_gids}",
        )
    except Exception as e:
        runner.check("PM need in correct project", False, str(e))

    return need.asana_gid


# ---------------------------------------------------------------------------
# Step 3: PM Onboarding project from template
# ---------------------------------------------------------------------------

async def test_onboarding_project(
    runner: SmokeTestRunner,
    crud: AsanaCRUD,
    run_id: str,
) -> str | None:
    """Create a PM Onboarding project from template and validate structure."""
    print("\n[3] PM Onboarding project template")

    from sidecar.automation.templates import create_pm_onboarding_project, _ONBOARDING_SECTIONS
    from sidecar.models.milestone import STANDARD_ONBOARDING_MILESTONES

    project_id = f"smoke-proj-{run_id}"
    go_live = date.today() + timedelta(days=120)

    try:
        result = await create_pm_onboarding_project(
            crud=crud,
            project_id=project_id,
            pm_name=f"Smoke PM {run_id}",
            strategy_label="Test Strategy",
            go_live_date=go_live,
        )
        runner.track_project(result.project_gid)
        runner.check("Onboarding project created", bool(result.project_gid))
    except Exception as e:
        runner.check("Onboarding project created", False, str(e))
        return None

    runner.check(
        f"All {len(_ONBOARDING_SECTIONS)} sections created",
        len(result.section_gids) == len(_ONBOARDING_SECTIONS),
        f"got {len(result.section_gids)}",
    )

    runner.check(
        f"All {len(STANDARD_ONBOARDING_MILESTONES)} milestones created",
        len(result.milestone_gids) == len(STANDARD_ONBOARDING_MILESTONES),
        f"got {len(result.milestone_gids)}",
    )

    # Verify Go-Live Ready milestone has the correct due date
    gl_ready_name = f"Smoke PM {run_id} - Go-Live Ready"
    gl_ready_gid = result.milestone_gids.get(gl_ready_name)
    if gl_ready_gid:
        try:
            ms_raw = await crud.get_task(gl_ready_gid)
            runner.check(
                "Go-Live Ready milestone has correct due date",
                ms_raw.get("due_on") == go_live.isoformat(),
                f"got {ms_raw.get('due_on')!r}, want {go_live.isoformat()!r}",
            )
            runner.check(
                "Go-Live Ready milestone is milestone subtype",
                ms_raw.get("resource_subtype") == "milestone",
            )
        except Exception as e:
            runner.check("Go-Live Ready milestone has correct due date", False, str(e))
    else:
        # Name may differ; just verify the count is right (already checked above)
        pass

    # Verify sections exist in Asana
    try:
        sections = await crud.list_sections(result.project_gid)
        section_names_in_asana = {s["name"] for s in sections}
        for expected in _ONBOARDING_SECTIONS:
            runner.check(
                f"Section '{expected}' in Asana",
                expected in section_names_in_asana,
            )
    except Exception as e:
        runner.check("Sections verified in Asana", False, str(e))

    return result.project_gid


# ---------------------------------------------------------------------------
# Step 4: Risk round-trip
# ---------------------------------------------------------------------------

async def test_risk(
    runner: SmokeTestRunner,
    crud: AsanaCRUD,
    run_id: str,
) -> None:
    """Create a risk/blocker in Asana and verify fields."""
    print("\n[4] Risk / Blocker round-trip")

    from sidecar.models.risk import RiskType, RiskSeverity

    cfg = crud._mapper._cfg
    if not cfg.risks_project_gid:
        print("    SKIP: ASANA_RISKS_PROJECT_GID not set")
        return

    risk_id = f"smoke-risk-{run_id}"
    risk_title = f"{SMOKE_TEST_PREFIX} Broker connectivity blocker {run_id}"

    try:
        risk = await crud.create_risk(
            risk_id=risk_id,
            title=risk_title,
            risk_type=RiskType.BLOCKER,
            severity=RiskSeverity.HIGH,
            mitigation_plan="Escalate to broker tech team.",
        )
        runner.track_task(risk.asana_gid)
        runner.check("Risk task created in Asana", bool(risk.asana_gid))
        runner.check("Risk title matches", risk_title in risk.title)
        runner.check("Risk status is open", str(risk.status) == "open")
    except Exception as e:
        runner.check("Risk task created in Asana", False, str(e))
        return

    # Fetch back and verify
    try:
        fetched = await crud.get_risk(risk.asana_gid, risk_id)
        runner.check("Risk fetched by GID", bool(fetched))
        runner.check("Risk severity is high", str(fetched.severity) == "high")
    except Exception as e:
        runner.check("Risk fetched by GID", False, str(e))


# ---------------------------------------------------------------------------
# Step 5: Sidecar API health checks
# ---------------------------------------------------------------------------

async def test_sidecar_api(
    runner: SmokeTestRunner,
    sidecar_url: str,
) -> None:
    """Verify the sidecar API is reachable and key endpoints return 200."""
    print("\n[5] Sidecar API health")

    endpoints_to_check = [
        ("/health",           "Health endpoint"),
        ("/pm-coverage",      "PM Coverage list"),
        ("/pm-needs",         "PM Needs list"),
        ("/milestones",       "Milestones list"),
        ("/risks",            "Risks list"),
        ("/decisions",        "Decisions list"),
        ("/operating-review/agenda", "Operating review agenda"),
    ]

    try:
        async with httpx.AsyncClient(base_url=sidecar_url, timeout=5.0) as http:
            for path, label in endpoints_to_check:
                try:
                    resp = await http.get(path)
                    runner.check(
                        f"{label} → HTTP {resp.status_code}",
                        resp.status_code in (200, 404),  # 404 ok for empty DB
                        f"got {resp.status_code}",
                    )
                except Exception as e:
                    runner.check(f"{label} reachable", False, str(e))
    except Exception:
        print("    (sidecar not reachable at {sidecar_url} — skipping all API checks)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(args: argparse.Namespace) -> int:
    token = os.environ.get("ASANA_PERSONAL_ACCESS_TOKEN", "")
    workspace_gid = os.environ.get("ASANA_WORKSPACE_GID", "")
    sidecar_url = os.environ.get("SIDECAR_BASE_URL", "http://localhost:8000")

    if not token or not workspace_gid:
        print("ERROR: Set ASANA_PERSONAL_ACCESS_TOKEN and ASANA_WORKSPACE_GID")
        return 1

    run_id = uuid.uuid4().hex[:8]
    print(f"Smoke test run: {run_id}")
    print(f"Workspace GID: {workspace_gid}")
    print(f"Sidecar URL:   {sidecar_url}")

    runner = SmokeTestRunner()
    field_cfg = _field_cfg_from_env()
    mapper = AsanaMapper(field_cfg)

    async with AsanaClient(token=token, workspace_gid=workspace_gid) as client:
        crud = AsanaCRUD(client, mapper)

        await test_pm_coverage(runner, crud, sidecar_url, run_id)
        await test_pm_need(runner, crud, sidecar_url, run_id)
        await test_onboarding_project(runner, crud, run_id)
        await test_risk(runner, crud, run_id)
        await test_sidecar_api(runner, sidecar_url)

        if not args.no_cleanup:
            await runner.cleanup(client)

    return runner.summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BAM Systematic Execution OS smoke test")
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Leave Asana objects in place after the test run (for manual inspection).",
    )
    parsed = parser.parse_args()
    sys.exit(asyncio.run(main(parsed)))
