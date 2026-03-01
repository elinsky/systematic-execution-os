"""PM Coverage API router.

GET  /pm-coverage          List all PM Coverage records
GET  /pm-coverage/{pm_id}  PM status summary
POST /pm-coverage          Create a new PM Coverage record
"""

from fastapi import APIRouter

router = APIRouter()

# TODO (Task #12): Implement endpoints delegating to pm_coverage_service.
