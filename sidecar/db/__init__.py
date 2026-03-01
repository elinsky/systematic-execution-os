"""SQLAlchemy ORM table definitions for the sidecar database.

Import all table modules here so that SQLAlchemy's metadata is populated
before create_all() is called.
"""

from sidecar.db import (
    capability,  # noqa: F401
    decision,  # noqa: F401
    milestone,  # noqa: F401
    pm_coverage,  # noqa: F401
    pm_need,  # noqa: F401
    project,  # noqa: F401
    risk,  # noqa: F401
)
