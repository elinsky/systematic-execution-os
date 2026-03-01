"""One-time workspace setup helper.

After the Phase 1 Asana workspace is configured, run this script to:
1. Query the Asana API for custom field GIDs by name.
2. Print .env export lines to paste into your .env file.

Usage:
    uv run python scripts/seed_config.py

Requires ASANA_PERSONAL_ACCESS_TOKEN and ASANA_WORKSPACE_GID to be set
in your environment or .env file.
"""

import asyncio
import os
import sys

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    # TODO: Implement custom field GID discovery once asana_client.py is available.
    print("seed_config.py: Asana client not yet implemented. See Task #9.")
    print("Once implemented, this script will print .env lines for all custom field GIDs.")


if __name__ == "__main__":
    asyncio.run(main())
