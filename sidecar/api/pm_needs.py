"""PM Needs API router.

GET   /pm-needs             List PM needs (filterable by PM, status, category)
POST  /pm-needs             Create PM need (creates Asana task + sidecar record)
PATCH /pm-needs/{need_id}   Update need status / metadata
"""

from fastapi import APIRouter

router = APIRouter()

# TODO (Task #12): Implement endpoints delegating to pm_need_service.
