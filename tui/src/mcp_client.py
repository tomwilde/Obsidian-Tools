from __future__ import annotations

from typing import Any, TypedDict

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent


class ToolInfo(TypedDict):
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolResult(TypedDict):
    is_error: bool
    text: str


class McpClient:
    """Async client wrapper around an MCP server exposed over Streamable HTTP."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._transport: Any = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "McpClient":
        self._transport = streamable_http_client(self._url)
        read_stream, write_stream = await self._transport.__aenter__()
        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        close_error: Exception | None = None

        if self._session is not None:
            try:
                await self._session.__aexit__(exc_type, exc, tb)
            except Exception as err:
                if "Session termination failed: 404" not in str(err):
                    close_error = err
            finally:
                self._session = None

        if self._transport is not None:
            try:
                await self._transport.__aexit__(exc_type, exc, tb)
            except Exception as err:
                if close_error is None:
                    close_error = err
            finally:
                self._transport = None

        if close_error is not None:
            raise close_error

    async def list_tools(self) -> list[ToolInfo]:
        if self._session is None:
            raise RuntimeError("MCP connection not open")
        result = await self._session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.input_schema or {},
            }
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        if self._session is None:
            raise RuntimeError("MCP connection not open")
        result = await self._session.call_tool(name, arguments or {})
        text = "\n".join(
            block.text for block in result.content if isinstance(block, TextContent) and block.text
        )
        return {"is_error": bool(result.is_error), "text": text}
