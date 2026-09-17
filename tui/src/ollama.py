"""Minimal OpenAI-style client for a local Ollama server."""

from __future__ import annotations

from typing import Any, AsyncIterator

from openai import AsyncOpenAI

Event = dict[str, Any]
"""Stream events: {"type": "delta", "content": str} then a final {"type": "message", "message": {...}}"""


class OllamaClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url
        self.model = model
        self._client = AsyncOpenAI(base_url=base_url, api_key="ollama")

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[Event]:
        """Stream a chat completion. Emits text deltas, then the assembled assistant message."""
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools or None,
            stream=True,
            stream_options={"include_usage": False},
        )

        content_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if delta.content:
                content_parts.append(delta.content)
                yield {"type": "delta", "content": delta.content}
            for tool_call in delta.tool_calls or []:
                index = tool_call.index
                call = tool_calls.setdefault(
                    index,
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    },
                )
                if tool_call.id:
                    call["id"] += tool_call.id
                if tool_call.function:
                    if tool_call.function.name:
                        call["function"]["name"] += tool_call.function.name
                    if tool_call.function.arguments:
                        call["function"]["arguments"] += tool_call.function.arguments

        message: dict[str, Any] = {"role": "assistant", "content": "".join(content_parts) or None}
        if tool_calls:
            message["tool_calls"] = [tool_calls[index] for index in sorted(tool_calls)]
        yield {"type": "message", "message": message}