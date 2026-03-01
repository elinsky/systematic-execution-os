"""Projects API router.

GET /projects               List projects (filterable by health, PM)
GET /projects/{project_id}  Project detail (milestones, blockers, decisions)
"""

from fastapi import APIRouter

router = APIRouter()

# TODO (Task #12): Implement endpoints delegating to project_service.
