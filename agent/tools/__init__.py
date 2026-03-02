"""MCP tools wrapping the sidecar REST API."""

from agent.tools.decisions import create_decision, list_decisions, resolve_decision
from agent.tools.health import check_health
from agent.tools.milestones import list_milestones, update_milestone
from agent.tools.pm_coverage import (
    create_pm_coverage,
    get_pm_coverage,
    list_pm_coverage,
    update_pm_coverage,
)
from agent.tools.pm_needs import (
    create_pm_need,
    get_pm_need,
    list_pm_needs,
    update_pm_need,
)
from agent.tools.projects import (
    get_project,
    get_project_milestones,
    list_projects,
    update_project,
)
from agent.tools.reports import (
    get_operating_review_agenda,
    get_pm_dashboard,
    get_portfolio_health,
    get_weekly_status_report,
)
from agent.tools.risks import create_risk, list_risks, update_risk

ALL_TOOLS = [
    # Read-only
    list_pm_coverage,
    get_pm_coverage,
    list_pm_needs,
    get_pm_need,
    list_projects,
    get_project,
    get_project_milestones,
    list_milestones,
    list_risks,
    list_decisions,
    get_operating_review_agenda,
    get_weekly_status_report,
    get_pm_dashboard,
    get_portfolio_health,
    check_health,
    # Write
    create_pm_coverage,
    update_pm_coverage,
    create_pm_need,
    update_pm_need,
    update_project,
    update_milestone,
    create_risk,
    update_risk,
    create_decision,
    resolve_decision,
]
