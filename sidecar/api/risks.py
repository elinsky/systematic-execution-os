"""Risks API router.

GET   /risks             List open risks/blockers (filterable by severity, PM)
POST  /risks             Create risk/blocker
PATCH /risks/{risk_id}   Update risk status
"""

from fastapi import APIRouter

router = APIRouter()

# TODO (Task #12): Implement endpoints delegating to risk_service.
