# Obsidian MCP

Talk to an **Obsidian vault** through [MCP](https://modelcontextprotocol.io).
A FastAPI MCP server (`server/`) exposes the vault as tools (list / read files,
folders, RAG queries), and a [Textual](https://textualize.io) terminal chat
(`tui/`) lets a **local Ollama** model call those tools to answer questions —
all running locally, no cloud APIs.

```
┌──────────────┐   MCP Streamable HTTP   ┌──────────────────┐
│  TUI (Textual)│ ──────────────────────▶ │  MCP Server      │
│  chat + tools │                         │  (vault tools)   │
└──────┬───────┘                         └──────────────────┘
       │  OpenAI-style streaming (tool calling)
       ▼
  ┌──────────────┐
  │  Ollama      │   local model
  └──────────────┘
```

---

## Prerequisites

- Python 3.13+ with [`uv`](https://docs.astral.sh/uv/)
- **Ollama** running locally on `http://localhost:11434` with a tools-capable
  model pulled, e.g. `gemma4:12b-it-qat`
- (optional) the RAG features use ChromaDB, installed automatically

## Configure the vault

Each side reads its options from the environment; set them once in your shell
before running, or use the flags/CLI below.

| Variable      | Server | TUI                      | Default                                |
|---------------|--------|--------------------------|----------------------------------------|
| `OBSIDIAN_DIR`| vault  | —                        | `D:\Dev\Projects\Roadmap\Data\Omni`    |
| `MCP_URL`     | —      | MCP server URL           | `http://localhost:8000/mcp`            |
| `OLLAMA_URL`  | —      | Ollama OpenAI endpoint   | `http://localhost:11434/v1`            |
| `OLLAMA_MODEL`| —      | model name               | `gemma4:12b-it-qat`                    |

---

## Run the MCP server

```bash
cd server
uv run uvicorn main:app --app-dir src --host 127.0.0.1 --port 8000
```

The server mounts the MCP Streamable HTTP endpoint at **`/mcp`** and serves a
health check at `/health`. Verify:

```bash
curl http://localhost:8000/health        # -> {"status":"healthy"}
```

## Run the TUI

With the server and Ollama both up, from a second terminal:

```bash
cd tui
uv run python src/main.py
```

You can override any of the three options with flags:

```bash
uv run python src/main.py \
    --mcp-url http://localhost:8000/mcp \
    --ollama-url http://localhost:11434/v1 \
    --model gemma4:12b-it-qat
```

### Using the TUI

- **Left pane:** the vault tools appear automatically after connecting. Select a
  tool, type JSON arguments, tab to **Call tool**, and see the raw result.
- **Right pane:** type a question about your vault. The assistant streams its
  reply and calls MCP tools on its own when it needs to inspect the vault —
  each tool call and its raw output is shown in the thread. Interrupt a running
  reply by typing a new message.

---

## Tests

```bash
cd server && uv run pytest     # server tests
cd tui    && uv run pytest     # TUI tests (headless + mocked network)
```
