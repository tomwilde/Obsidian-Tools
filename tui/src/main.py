"""Textual TUI for the Obsidian MCP server backed by local Ollama.

Run from this directory with:

    uv run python src/main.py [--mcp-url ...] [--ollama-url ...] [--model ...]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Markdown, Static, TextArea

from chat import MAX_TOOL_ROUNDS, SYSTEM_PROMPT, build_default_arguments, parse_arguments, to_openai_tools
from mcp_client import McpClient, ToolInfo
from ollama import OllamaClient

DEFAULT_MCP_URL = "http://localhost:8000/mcp"
DEFAULT_OLLAMA_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "gemma4:12b-it-qat"


class ObsidianTui(App):
    TITLE = "Obsidian MCP TUI"
    SUB_TITLE = "Ollama + MCP"

    CSS = """
    Screen > #main {
        height: 1fr;
    }

    #tool-pane {
        width: 44;
        border-right: solid $primary;
        padding: 0 1;
    }

    #tool-pane #status {
        height: 1;
        color: $text-muted;
        margin-bottom: 1;
        overflow-x: hidden;
    }

    #tool-list {
        height: 1fr;
        max-height: 12;
        border: solid $accent;
        margin-bottom: 1;
    }

    #tool-desc-scroll {
        height: 8;
        border: solid $panel;
        margin-bottom: 1;
        overflow-y: auto;
    }

    #tool-desc {
        width: 100%;
        padding: 0 1;
    }

    #args-input {
        height: 12;
        border: solid $accent;
        padding: 0 1;
        margin-bottom: 1;
        overflow-y: auto;
    }

    #call-btn {
        margin-bottom: 1;
    }

    #tool-result-scroll {
        height: 1fr;
        border: solid $panel;
    }

    #tool-result {
        width: 100%;
        padding: 0 1;
    }

    #chat-pane {
        width: 1fr;
        padding: 0 1;
    }

    #chat-scroll {
        height: 1fr;
        border: solid $panel;
        overflow-y: auto;
    }

    #chat {
        width: 100%;
        padding: 1;
    }

    #chat-input {
        margin-top: 1;
    }
    """

    def __init__(self, mcp_url: str, ollama_url: str, model: str) -> None:
        super().__init__()
        self.mcp_url = mcp_url
        self.ollama = OllamaClient(ollama_url, model)
        self.model = model
        self.mcp: McpClient | None = None
        self.tools: list[ToolInfo] = []
        self._mcp_task: asyncio.Task[None] | None = None
        self._mcp_close_event = asyncio.Event()
        self._selected_tool: ToolInfo | None = None
        self._chat_worker: Any = None
        self._history: list[dict[str, Any]] = []
        self._blocks: list[str] = []
        self._stream = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="tool-pane"):
                yield Static("Connecting…", id="status")
                yield Label("Tools")
                yield ListView(
                    ListItem(Label("Connecting to MCP server…")),
                    id="tool-list",
                )
                with ScrollableContainer(id="tool-desc-scroll"):
                    yield Static("Select a tool above.", id="tool-desc")
                yield TextArea("{}", id="args-input", language="json")
                yield Button("Call tool", id="call-btn", variant="primary")
                with ScrollableContainer(id="tool-result-scroll"):
                    yield Static("", id="tool-result")
            with Vertical(id="chat-pane"):
                with ScrollableContainer(id="chat-scroll"):
                    yield Markdown("Ask about your vault below. The assistant can call MCP tools.", id="chat")
                yield Input(placeholder="Ask about your vault…", id="chat-input")
        yield Footer()

    def on_mount(self) -> None:
        self._mcp_task = asyncio.create_task(self._connect())
        self.query_one("#chat-input", Input).focus()

    async def on_unmount(self) -> None:
        self._mcp_close_event.set()
        if self._mcp_task is None:
            return
        try:
            await self._mcp_task
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------ mcp

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    async def _connect(self) -> None:
        self._set_status(f"Connecting to {self.mcp_url}…")
        client = McpClient(self.mcp_url)
        connected = False

        try:
            async with client:
                connected = True
                self.mcp = client
                try:
                    self.tools = await self.mcp.list_tools()
                except Exception as exc:
                    self._set_status(f"Failed to list tools: {exc}")
                    return

                items = [ListItem(Label(tool["name"])) for tool in self.tools]
                for item, tool in zip(items, self.tools):
                    item.tool_info = tool
                await self._replace_tool_list(items)
                self._set_status(f"Connected · {len(self.tools)} tool(s)")

                await self._mcp_close_event.wait()
        except Exception as exc:
            if not connected:
                self._set_status(f"MCP connection failed: {exc}")
                await self._replace_tool_list([ListItem(Label(f"Connection failed: {exc}"))])
                return
            if not self._mcp_close_event.is_set():
                self._set_status(f"MCP session closed with error: {exc}")
        finally:
            self.mcp = None

    async def _replace_tool_list(self, items: list[ListItem]) -> None:
        tool_list = self.query_one("#tool-list", ListView)
        await tool_list.clear()
        for item in items:
            await tool_list.append(item)

    @on(ListView.Selected, "#tool-list")
    def _on_tool_selected(self, event: ListView.Selected) -> None:
        item = event.item
        tool: ToolInfo | None = getattr(item, "tool_info", None)
        if tool is None:
            return
        self._selected_tool = tool
        schema = json.dumps(tool["input_schema"], indent=2)
        desc = f"**{tool['name']}**\n{tool['description'] or '(no description)'}\n\n```json\n{schema}\n```"
        self.query_one("#tool-desc", Static).update(desc)
        self.query_one("#args-input", TextArea).text = json.dumps(
            build_default_arguments(tool.get("input_schema")), indent=2
        )
        self.query_one("#tool-result", Static).update("Set JSON arguments below, then **Call tool**.")

    @on(Button.Pressed, "#call-btn")
    def _on_call_button(self) -> None:
        self._call_selected_tool()

    def _call_selected_tool(self) -> None:
        if self._selected_tool is None:
            self.query_one("#tool-result", Static).update("Select a tool first.")
            return
        if self.mcp is None:
            self.query_one("#tool-result", Static).update("MCP server not connected.")
            return
        raw = self.query_one("#args-input", TextArea).text or "{}"
        try:
            arguments = parse_arguments(raw)
        except ValueError as exc:
            self.query_one("#tool-result", Static).update(f"**[Error]** {exc}")
            return
        self.query_one("#call-btn", Button).disabled = True
        self.run_worker(
            self._call_tool(self._selected_tool, arguments),
            group="call",
            exclusive=True,
            thread=False,
        )

    async def _call_tool(self, tool: ToolInfo, arguments: dict[str, Any]) -> None:
        result_static = self.query_one("#tool-result", Static)
        result_static.update(f"_Calling **{tool['name']}**…_")
        try:
            assert self.mcp is not None
            outcome = await self.mcp.call_tool(tool["name"], arguments)
        except Exception as exc:
            result_static.update(f"**[Error]** {exc}")
        else:
            result_static.update(f"**{tool['name']}** →\n\n{outcome['text'] or '(no text result)'}")
        finally:
            self.query_one("#call-btn", Button).disabled = False

    # ------------------------------------------------------------------ chat

    async def _render_chat(self) -> None:
        markdown = self.query_one("#chat", Markdown)
        chat_scroll = self.query_one("#chat-scroll", ScrollableContainer)
        parts = list(self._blocks)
        if self._stream:
            parts.append(self._stream)
        text = "\n\n".join(parts)
        await markdown.update(text + "\n")
        chat_scroll.scroll_end(animate=False)

    @on(Input.Submitted, "#chat-input")
    def _on_chat_submitted(self, event: Input.Submitted) -> None:
        prompt = (event.value or "").strip()
        if not prompt:
            return
        event.input.value = ""
        if self._chat_worker is not None:
            self._chat_worker.cancel()
        self._chat_worker = self.run_worker(
            self._chat(prompt), group="chat", exclusive=True, thread=False
        )

    async def _chat(self, prompt: str) -> None:
        chat_input = self.query_one("#chat-input", Input)
        if self.mcp is None:
            self._blocks.append(f"**You**\n\n{prompt}")
            self._blocks.append("**[Error]** MCP server not connected.")
            await self._render_chat()
            return

        chat_input.disabled = True
        self._history.append({"role": "user", "content": prompt})
        self._blocks.append(f"**You**\n\n{prompt}")
        await self._render_chat()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ] + self._history
        tool_schemas = to_openai_tools(self.tools) if self.tools else None
        retried_without_tools = False
        assist_content = ""
        failed = False

        try:
            for _ in range(MAX_TOOL_ROUNDS):
                message: dict[str, Any] | None = None
                try:
                    async for event in self.ollama.stream_chat(messages, tools=tool_schemas):
                        if event["type"] == "delta":
                            self._stream += event["content"]
                            await self._render_chat()
                        else:
                            message = event["message"]
                except Exception as exc:
                    if tool_schemas and not retried_without_tools:
                        retried_without_tools = True
                        tool_schemas = None
                        self._stream = "_Model rejected tool calling; retrying without tools._\n\n"
                        await self._render_chat()
                        continue
                    self._blocks.append(f"**[Error]** {exc}")
                    failed = True
                    break

                if message is None:
                    failed = True
                    break
                messages.append(message)

                tool_calls = message.get("tool_calls")
                if not tool_calls:
                    assist_content = message.get("content") or ""
                    break

                for tool_call in tool_calls:
                    name = tool_call["function"]["name"]
                    raw_arguments = tool_call["function"]["arguments"] or "{}"
                    try:
                        arguments = parse_arguments(raw_arguments)
                    except ValueError:
                        arguments = {}
                    self._blocks.append(f"**Tool: {name}**")
                    self._blocks.append(f"```json\n{raw_arguments}\n```")
                    self._stream = ""
                    await self._render_chat()
                    outcome = await self.mcp.call_tool(name, arguments)
                    self._blocks.append(outcome["text"] or "(no text result)")
                    self._stream = ""
                    await self._render_chat()
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id") or f"{name}:{_ + 1}",
                            "content": outcome["text"] or "(no text result)",
                        }
                    )
        finally:
            if not failed:
                if assist_content:
                    self._blocks.append(f"**Assistant**\n\n{assist_content}")
                else:
                    self._blocks.append("**[Assistant]** _No response._")
                self._history.append({"role": "assistant", "content": assist_content})
            self._stream = ""
            await self._render_chat()
            chat_input.disabled = False
            chat_input.focus()

        self._history = self._history[-60:]


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Obsidian MCP TUI")
    parser.add_argument(
        "--mcp-url",
        default=os.environ.get("MCP_URL", DEFAULT_MCP_URL),
        help="MCP server URL (default: %(default)s)",
    )
    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL),
        help="OpenAI-style Ollama base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL),
        help="Ollama model to use (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    ObsidianTui(args.mcp_url, args.ollama_url, args.model).run()


if __name__ == "__main__":
    run()
