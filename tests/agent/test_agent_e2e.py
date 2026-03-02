"""E2E tests for agent setup — validates wiring without live sidecar."""

from __future__ import annotations

from agent.agent_setup import MCP_SERVER_NAME, build_mcp_server, build_options
from agent.system_prompt import SYSTEM_PROMPT
from agent.tools import ALL_TOOLS


class TestToolInventory:
    """Verify all 25 tools are registered."""

    def test_all_tools_count(self):
        assert len(ALL_TOOLS) == 25

    def test_tool_names_unique(self):
        names = [t.name for t in ALL_TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_read_tools_count(self):
        read_tools = [t for t in ALL_TOOLS if "[WRITE]" not in t.description]
        assert len(read_tools) == 15

    def test_write_tools_count(self):
        write_tools = [t for t in ALL_TOOLS if "[WRITE]" in t.description]
        assert len(write_tools) == 10

    def test_write_tools_have_confirm_instruction(self):
        write_tools = [t for t in ALL_TOOLS if "[WRITE]" in t.description]
        for tool in write_tools:
            assert "CONFIRM" in tool.description, (
                f"Write tool '{tool.name}' missing CONFIRM instruction"
            )


class TestMCPServer:
    def test_build_mcp_server(self):
        server = build_mcp_server()
        assert server is not None


class TestAgentOptions:
    def test_build_options(self):
        options = build_options()
        assert options.system_prompt == SYSTEM_PROMPT
        assert MCP_SERVER_NAME in options.mcp_servers
        assert len(options.allowed_tools) == 25

    def test_allowed_tools_follow_naming_convention(self):
        options = build_options()
        for tool_name in options.allowed_tools:
            assert tool_name.startswith(f"mcp__{MCP_SERVER_NAME}__"), (
                f"Tool name '{tool_name}' doesn't follow convention"
            )
