"""Manual full-sync from Asana.

Pulls all objects from the configured singleton Asana projects into the sidecar DB.
Use this for initial setup or to recover from a missed webhook window.

Usage:
    uv run python scripts/backfill_sync.py

Requires a populated .env file (run scripts/seed_config.py first).

What is synced:
    - All tasks in the PM Coverage Board project
    - All tasks in the PM Needs project
    - All tasks in the Risks & Blockers project
    - All tasks (milestones only) in each active onboarding/capability project

Sidecar IDs: the backfill generates sidecar IDs as f"asana-{gid}" for any
objects that don't yet have a sidecar ID. These can be updated later via the
sidecar API if you prefer human-readable IDs.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sidecar.config import Settings
from sidecar.integrations.asana.client import AsanaClient, TASK_OPT_FIELDS
from sidecar.integrations.asana.mapper import AsanaFieldConfig, AsanaMapper
from sidecar.integrations.asana_sync import (
    pull_sync_pm_coverage_task,
    pull_sync_pm_need_task,
    pull_sync_risk,
    pull_sync_milestone,
)


def _field_cfg(settings: Settings) -> AsanaFieldConfig:
    g = lambda key: getattr(settings, key, None) or os.environ.get(f"ASANA_CUSTOM_FIELD_{key.upper()}")
    return AsanaFieldConfig(
        health_gid=os.environ.get("ASANA_CUSTOM_FIELD_HEALTH"),
        region_gid=os.environ.get("ASANA_CUSTOM_FIELD_REGION"),
        last_touchpoint_gid=os.environ.get("ASANA_CUSTOM_FIELD_LAST_TOUCHPOINT"),
        onboarding_stage_gid=os.environ.get("ASANA_CUSTOM_FIELD_ONBOARDING_STAGE"),
        need_category_gid=os.environ.get("ASANA_CUSTOM_FIELD_NEED_CATEGORY"),
        urgency_gid=os.environ.get("ASANA_CUSTOM_FIELD_URGENCY"),
        business_impact_gid=os.environ.get("ASANA_CUSTOM_FIELD_BUSINESS_IMPACT"),
        need_status_gid=os.environ.get("ASANA_CUSTOM_FIELD_NEED_STATUS"),
        milestone_status_gid=os.environ.get("ASANA_CUSTOM_FIELD_MILESTONE_STATUS"),
        milestone_confidence_gid=os.environ.get("ASANA_CUSTOM_FIELD_CONFIDENCE"),
        risk_type_gid=os.environ.get("ASANA_CUSTOM_FIELD_ITEM_TYPE"),
        severity_gid=os.environ.get("ASANA_CUSTOM_FIELD_SEVERITY"),
        escalation_status_gid=os.environ.get("ASANA_CUSTOM_FIELD_ESCALATION_STATUS"),
        pm_coverage_project_gid=os.environ.get("ASANA_PM_COVERAGE_PROJECT_GID"),
        pm_needs_project_gid=os.environ.get("ASANA_PM_NEEDS_PROJECT_GID"),
        risks_project_gid=os.environ.get("ASANA_RISKS_PROJECT_GID"),
    )


async def sync_pm_coverage(
    client: AsanaClient,
    session: AsyncSession,
    field_cfg: AsanaFieldConfig,
) -> int:
    project_gid = field_cfg.pm_coverage_project_gid
    if not project_gid:
        print("  SKIP: ASANA_PM_COVERAGE_PROJECT_GID not set")
        return 0
    count = 0
    async for task in client.paginate(
        f"projects/{project_gid}/tasks",
        params={"opt_fields": TASK_OPT_FIELDS},
    ):
        gid = task.get("gid", "")
        if not gid:
            continue
        pm_id = f"asana-{gid}"
        await pull_sync_pm_coverage_task(session, task, pm_id, field_cfg)
        count += 1
    return count


async def sync_pm_needs(
    client: AsanaClient,
    session: AsyncSession,
    field_cfg: AsanaFieldConfig,
) -> int:
    project_gid = field_cfg.pm_needs_project_gid
    if not project_gid:
        print("  SKIP: ASANA_PM_NEEDS_PROJECT_GID not set")
        return 0
    count = 0
    async for task in client.paginate(
        f"projects/{project_gid}/tasks",
        params={"opt_fields": TASK_OPT_FIELDS},
    ):
        gid = task.get("gid", "")
        if not gid:
            continue
        need_id = f"asana-need-{gid}"
        pm_id = f"asana-pm-unknown"  # will be resolved by service layer later
        await pull_sync_pm_need_task(session, task, need_id, pm_id, field_cfg)
        count += 1
    return count


async def sync_risks(
    client: AsanaClient,
    session: AsyncSession,
    field_cfg: AsanaFieldConfig,
) -> int:
    project_gid = field_cfg.risks_project_gid
    if not project_gid:
        print("  SKIP: ASANA_RISKS_PROJECT_GID not set")
        return 0
    count = 0
    async for task in client.paginate(
        f"projects/{project_gid}/tasks",
        params={"opt_fields": TASK_OPT_FIELDS},
    ):
        gid = task.get("gid", "")
        if not gid:
            continue
        risk_id = f"asana-risk-{gid}"
        await pull_sync_risk(session, task, risk_id, field_cfg)
        count += 1
    return count


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    field_cfg = _field_cfg(settings)

    engine = create_async_engine(settings.database_url, echo=False)

    import sidecar.db  # noqa: F401 — register all ORM models
    from sidecar.db.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsanaClient(
        token=settings.asana_personal_access_token,
        workspace_gid=settings.asana_workspace_gid,
    ) as client:
        async with factory() as session:
            print("Syncing PM Coverage Board...")
            n = await sync_pm_coverage(client, session, field_cfg)
            print(f"  {n} PM coverage records synced")

            print("Syncing PM Needs...")
            n = await sync_pm_needs(client, session, field_cfg)
            print(f"  {n} PM needs synced")

            print("Syncing Risks & Blockers...")
            n = await sync_risks(client, session, field_cfg)
            print(f"  {n} risks synced")

            await session.commit()

    print("Backfill complete.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
