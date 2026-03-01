"""Operating Review API router.

GET /operating-review/agenda       Auto-generate weekly review agenda
GET /operating-review/at-risk-pms  PMs with active blockers or slipping milestones
"""

from fastapi import APIRouter

router = APIRouter()

# TODO (Task #12): Implement endpoints delegating to operating_review_service.
