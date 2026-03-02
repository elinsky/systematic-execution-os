"""Agent setup — create MCP server, register tools, build SDK client."""

from __future__ import annotations

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server

from agent.config import get_config
from agent.system_prompt import SYSTEM_PROMPT
from agent.tools import ALL_TOOLS

MCP_SERVER_NAME = "bam-sidecar"
MCP_SERVER_VERSION = "0.1.0"


def build_mcp_server():
    """Create an in-process MCP server with all sidecar tools registered."""
    return create_sdk_mcp_server(
        name=MCP_SERVER_NAME,
        version=MCP_SERVER_VERSION,
        tools=ALL_TOOLS,
    )


def build_options() -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with system prompt, MCP server, and model config."""
    cfg = get_config()
    server = build_mcp_server()

    # Build allowed tools list: all MCP tools
    tool_names = [f"mcp__{MCP_SERVER_NAME}__{t.name}" for t in ALL_TOOLS]

    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={MCP_SERVER_NAME: server},
        allowed_tools=tool_names,
        model=cfg.model,
    )


def create_client() -> ClaudeSDKClient:
    """Create a configured ClaudeSDKClient ready for conversations."""
    return ClaudeSDKClient(options=build_options())
