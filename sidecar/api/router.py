"""Top-level router that mounts all sub-routers."""

from fastapi import APIRouter

router = APIRouter()

# Sub-routers are imported and included here once implemented (Task #12).
# Stubs are registered now so the app boots cleanly.

from sidecar.api import (  # noqa: E402
    capabilities,
    decisions,
    milestones,
    operating_review,
    pm_coverage,
    pm_needs,
    projects,
    risks,
)

router.include_router(pm_coverage.router, prefix="/pm-coverage", tags=["pm-coverage"])
router.include_router(pm_needs.router, prefix="/pm-needs", tags=["pm-needs"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(milestones.router, prefix="/milestones", tags=["milestones"])
router.include_router(risks.router, prefix="/risks", tags=["risks"])
router.include_router(decisions.router, prefix="/decisions", tags=["decisions"])
router.include_router(capabilities.router, prefix="/capabilities", tags=["capabilities"])
router.include_router(
    operating_review.router, prefix="/operating-review", tags=["operating-review"]
)
