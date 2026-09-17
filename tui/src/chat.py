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

def build_default_arguments(input_schema: dict[str, Any] | None) -> dict[str, Any]:
    """Build a sensible default argument object from an MCP tool input schema.

    Every property named in the schema is given a JSON-typed placeholder
    (string -> "", boolean -> False, integer/number -> 0, array -> [], object ->
    {}) unless the schema declares an explicit default. Required-vs-optional is
    ignored here: tools should accept the full set so calls round trip even when
    the model omits arguments.
    """
    schema = input_schema or {}
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    defaults: dict[str, Any] = {}
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        if "default" in prop:
            defaults[name] = prop["default"]
            continue
        ptype = prop.get("type")
        if ptype == "string":
            defaults[name] = ""
        elif ptype in ("integer", "number"):
            defaults[name] = 0
        elif ptype == "boolean":
            defaults[name] = False
        elif ptype == "array":
            defaults[name] = []
        elif ptype == "object":
            defaults[name] = {}
        elif ptype is None and "$ref" in prop:
            defaults[name] = {}
    return defaults


