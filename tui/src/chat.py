"""Pure helpers shared between the TUI app and tests."""

from __future__ import annotations

import json
from typing import Any

from mcp_client import ToolInfo

MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT = (
    "You are a helpful assistant for an Obsidian vault. "
    "Use the provided tools to inspect, read, and search the vault when it helps "
    "answer the user's question. Answer concisely."
)


def to_openai_tools(tools: list[ToolInfo]) -> list[dict[str, Any]]:
    """Map MCP tool metadata to OpenAI function-calling tool schemas."""
    converted: list[dict[str, Any]] = []
    for tool in tools:
        parameters = tool.get("input_schema") or {"type": "object", "properties": {}}
        if parameters.get("type") != "object":
            parameters = {"type": "object", "properties": {}}
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description") or "",
                    "parameters": parameters,
                },
            }
        )
    return converted


def parse_arguments(raw: str) -> dict[str, Any]:
    """Parse a JSON argument blob, raising ValueError with a helpful message on failure."""
    text = raw.strip() or "{}"
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON arguments: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Arguments must be a JSON object")
    return value