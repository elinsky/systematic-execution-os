"""Decisions API router.

GET  /decisions            List decisions (filterable by status, project)
POST /decisions            Create decision record
"""

from fastapi import APIRouter

router = APIRouter()

# TODO (Task #12): Implement endpoints delegating to decision_service.
