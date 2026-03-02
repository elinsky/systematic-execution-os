"""Tests for system prompt content — verifies domain knowledge is complete."""

from agent.system_prompt import SYSTEM_PROMPT


class TestSystemPromptContent:
    """Validate that the system prompt contains all required domain knowledge."""

    def test_prompt_is_nonempty(self):
        assert len(SYSTEM_PROMPT) > 500

    # --- Onboarding stages ---
    def test_contains_all_onboarding_stages(self):
        stages = [
            "pipeline", "pre_start", "requirements_discovery",
            "onboarding_in_progress", "uat", "go_live_ready",
            "live", "stabilization", "steady_state",
        ]
        for stage in stages:
            assert stage in SYSTEM_PROMPT, f"Missing onboarding stage: {stage}"

    # --- Health statuses ---
    def test_contains_health_statuses(self):
        for status in ("green", "yellow", "red", "unknown"):
            assert status in SYSTEM_PROMPT, f"Missing health status: {status}"

    # --- Need categories ---
    def test_contains_need_categories(self):
        categories = [
            "market_data", "historical_data", "alt_data", "execution",
            "broker", "infra", "research", "ops", "other",
        ]
        for cat in categories:
            assert cat in SYSTEM_PROMPT, f"Missing need category: {cat}"

    # --- Risk types and severities ---
    def test_contains_risk_types(self):
        for rt in ("risk", "blocker", "issue"):
            assert rt in SYSTEM_PROMPT, f"Missing risk type: {rt}"

    def test_contains_risk_severities(self):
        for sev in ("critical", "high", "medium", "low"):
            assert sev in SYSTEM_PROMPT, f"Missing severity: {sev}"

    # --- Decision immutability rule ---
    def test_contains_decision_immutability_rule(self):
        assert "IMMUTABLE" in SYSTEM_PROMPT

    # --- PM need status read-only rule ---
    def test_contains_pm_need_status_rule(self):
        assert "status" in SYSTEM_PROMPT.lower()
        assert "read-only" in SYSTEM_PROMPT.lower() or "read only" in SYSTEM_PROMPT.lower()

    # --- Confirmation protocol ---
    def test_contains_confirmation_protocol(self):
        assert "confirm" in SYSTEM_PROMPT.lower()
        assert "[WRITE]" in SYSTEM_PROMPT

    # --- Entity types ---
    def test_contains_entity_types(self):
        for entity in ("PM Coverage", "PM Needs", "Projects", "Milestones",
                        "Risks", "Decisions"):
            assert entity in SYSTEM_PROMPT, f"Missing entity: {entity}"
