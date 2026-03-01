"""Manual full-sync from Asana.

Pulls all Asana objects (projects, milestones, tasks) into the sidecar DB.
Use this for initial setup or to recover from a missed webhook window.

Usage:
    uv run python scripts/backfill_sync.py

Requires a populated .env file.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    # TODO: Implement full backfill once asana_sync.py is available (Task #13).
    print("backfill_sync.py: Sync layer not yet implemented. See Task #13.")


if __name__ == "__main__":
    asyncio.run(main())
