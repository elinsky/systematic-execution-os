"""Agent configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    """Configuration for the BAM agent.

    All values can be overridden via environment variables (prefixed AGENT_)
    or a .env file.
    """

    model_config = {"env_prefix": "AGENT_", "env_file": ".env", "extra": "ignore"}

    sidecar_url: str = "http://localhost:8000"
    api_prefix: str = "/api/v1"
    api_timeout: float = 10.0
    model: str = "sonnet"

    @property
    def api_base(self) -> str:
        return f"{self.sidecar_url}{self.api_prefix}"


_config: AgentConfig | None = None


def get_config() -> AgentConfig:
    global _config
    if _config is None:
        _config = AgentConfig()
    return _config
