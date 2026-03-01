"""SQLAlchemy ORM table definitions for the sidecar database.

Import all table modules here so that SQLAlchemy's metadata is populated
before create_all() is called.
"""

from sidecar.db import pm_coverage  # noqa: F401
from sidecar.db import pm_need  # noqa: F401
from sidecar.db import project  # noqa: F401
from sidecar.db import milestone  # noqa: F401
from sidecar.db import risk  # noqa: F401
from sidecar.db import decision  # noqa: F401
from sidecar.db import capability  # noqa: F401
