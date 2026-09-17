# Obsidian MCP TUI

A [Textual](https://github.com/textualize/textual) terminal app that lets you chat
with your Obsidian vault through a **local MCP server**, powered by a **local
Ollama** model that can call the MCP tools itself.

## Layout

```
tui/
├── pyproject.toml          uv project · deps: textual, mcp, openai
├── src/
│   ├── main.py             Textual App (left pane: tools · right pane: chat)
│   ├── chat.py             pure helpers: OpenAI tool schemas, JSON args parsing
│   ├── mcp_client.py       async MCP client (Streamable HTTP)
│   └── ollama.py           OpenAI-style streaming client for Ollama
└── tests/
    ├── test_app.py         headless mount smoke tests (Textual pilot)
    ├── test_chat.py        schema mapping + stream/tool-call assembly
    └── test_ollama.py      ChatCompletion stream decoding
```

## Prerequisites

1. The **MCP server** running locally (default `http://localhost:8000`): run
   from `../server` the FastAPI app that exposes the Streamable HTTP endpoint.
2. **Ollama** running locally (`http://localhost:11434`) with a tools-capable
   model installed, e.g. `gemma4:12b-it-qat`.

## Run

```bash
uv run python src/main.py \
    --mcp-url http://localhost:8000/mcp \
    --ollama-url http://localhost:11434/v1 \
    --model gemma4:12b-it-qat
```

All three flags can also be set via the environment variables `MCP_URL`,
`OLLAMA_URL`, and `OLLAMA_MODEL`.

## Usage

- **Left pane:** the MCP server's tools are listed on startup. Select one, fill
  in JSON arguments, and press **Call tool** (or just scroll the list — the
  selection is remembered).
- **Right pane:** type a question about your vault. The assistant streams its
  reply and, when needed, calls MCP tools automatically (up to
  `MAX_TOOL_ROUNDS` rounds). Tool calls and their raw results are shown inline.
  You can interrupt a running reply by typing a new message.

## Tests

```bash
uv run pytest
```

Tests mock the network layers (no live server or Ollama needed).
