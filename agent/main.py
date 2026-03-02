"""Terminal REPL entry point for the BAM agent."""

from __future__ import annotations

import sys

import anyio
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

from agent.agent_setup import create_client


async def repl() -> None:
    """Run an interactive terminal REPL with the BAM agent."""
    print("BAM Systematic Execution OS — AI Agent")
    print("Type your questions or commands. Type 'quit' or 'exit' to stop.\n")

    async with create_client() as client:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit"):
                print("Goodbye!")
                break

            await client.query(user_input)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(f"\nAgent: {block.text}")
                        elif isinstance(block, ToolUseBlock):
                            print(f"\n  [calling {block.name}...]")
                elif isinstance(message, ResultMessage):
                    # Tool results are handled internally by the SDK
                    pass

            print()  # blank line between turns


def main() -> None:
    """Entry point."""
    try:
        anyio.run(repl)
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
