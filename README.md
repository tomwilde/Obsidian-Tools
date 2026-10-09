# Obsidian MCP

Talk to an **Obsidian vault** through [MCP](https://modelcontextprotocol.io).
A FastAPI MCP server (`server/`) exposes the vault as tools (list / read files,
folders, RAG queries), and a [Textual](https://textualize.io) terminal chat
(`tui/`) lets a **local Ollama** model call those tools to answer questions —
all running locally, no cloud APIs.

```
┌───────────────┐   MCP Streamable HTTP   ┌──────────────────┐
│  TUI (Textual)│ ──────────────────────▶ │  MCP Server      │
│  chat + tools │                         │  (vault tools)   │
└──────┬────────┘                         └──────────────────┘
       │  OpenAI-style streaming (tool calling)
       ▼
  ┌──────────────┐
  │  Ollama      │   local model
  └──────────────┘
```

---

## Layout & environment

Single **uv workspace** (`pyproject.toml` at the repo root with members
`["server", "tui"]`): `server/` and `tui/` share **one** venv (root `.venv`),
**one** `uv.lock`, and one interpreter. `uv run` from anywhere in the tree
resolves to the same shared environment — no per-project venvs.

## Prerequisites

- Python 3.13+ with [`uv`](https://docs.astral.sh/uv/)
- **Ollama** running locally on `http://localhost:11434` with a tools-capable
  model pulled, e.g. `gemma4:12b-it-qat`
- (optional) the RAG features use ChromaDB, installed automatically

Environment is set up once from the repo root:

```bash
uv sync                       # creates .venv + uv.lock (shared)
```

## Configure the vault

Each side reads its options from the environment; set them once in your shell
before running, or use the flags/CLI below.

| Variable      | Server | TUI                      | Default                                |
|---------------|--------|--------------------------|----------------------------------------|
| `VAULT_DIR`   | vault  | —                        | `RootDir` from `server/src/config.ini` |
| `EXCLUDED_DIRS` | excluded folders | —            | `ExcludedDirs` from `server/src/config.ini` |
| `MCP_URL`     | —      | MCP server URL           | `http://localhost:8000/mcp`            |
| `OLLAMA_URL`  | —      | Ollama OpenAI endpoint   | `http://localhost:11434/v1`            |
| `OLLAMA_MODEL`| —      | model name               | `gemma4:12b-it-qat`                    |

If `VAULT_DIR` is set, it overrides `RootDir` from `config.ini`. If
`EXCLUDED_DIRS` is set (including an empty value), it overrides
`ExcludedDirs` from `config.ini`.

To hide folders from both MCP tools and RAG indexing, set `ExcludedDirs` in
`server/src/config.ini` (comma- or newline-separated, vault-relative paths):

```ini
[Obsidian]
RootDir=/path/to/your/vault
ExcludedDirs=.obsidian,Templates/private
```

Any folder listed in `ExcludedDirs` is treated as non-existent externally: it
is not listed by tools, files under it cannot be read, and its markdown is not
indexed for RAG queries.

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

## Docker (single container: server + TUI harness)

Build from the repo root:

```bash
docker build -t tw-obsidian-tools .
```

Run with your local vault folder mounted in, and host Ollama reachable from
inside the container:

```bash
docker run --rm -it \
    -p 8000:8000 \
    --add-host=host.docker.internal:host-gateway \
    -v "$(pwd)/Vault:/data/Vault" \
    -e VAULT_DIR=/data/Vault \
    -e OLLAMA_URL=http://host.docker.internal:11434/v1 \
    -e OLLAMA_MODEL=gemma4:12b-it-qat \
    tw-obsidian-tools
```

Notes:

- This image runs both parts together: FastAPI MCP server + Textual TUI.
- The TUI talks to the in-container MCP server (`http://127.0.0.1:8000/mcp`).
- `--add-host=host.docker.internal:host-gateway` is required on Linux so the
  container can reach Ollama running on the host.
- For container-to-host access, Ollama should listen beyond loopback. A common
  setup is:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

### Docker Compose (recommended)

Compose reads root `.env` automatically. A starter `.env` is included; edit it
before first run:

```bash
cp .env.example .env  # optional if .env already exists
```

Set at least:

- `HOST_VAULT_DIR` to your local vault path
- `EXCLUDED_DIRS` if you want to hide folders from tools/RAG
- `OLLAMA_URL` / `OLLAMA_MODEL` to match your host Ollama setup

For the best interactive TUI sizing, use `run`:

```bash
docker compose run --rm --build --service-ports app
```

Defaults used by compose:

- `${HOST_VAULT_DIR}` mounted at `${CONTAINER_VAULT_DIR}`
- `VAULT_DIR=${CONTAINER_VAULT_DIR}`
- `EXCLUDED_DIRS=`
- `OLLAMA_URL=http://host.docker.internal:11434/v1`
- `OLLAMA_MODEL=gemma4:12b-it-qat`

To point at a different local vault path:

```bash
HOST_VAULT_DIR=/absolute/path/to/vault docker compose run --rm --build --service-ports app
```

To override vault exclusions and Ollama settings:

```bash
HOST_VAULT_DIR=/absolute/path/to/vault \
EXCLUDED_DIRS=.obsidian,Templates/private \
OLLAMA_URL=http://host.docker.internal:11434/v1 \
OLLAMA_MODEL=gemma4:12b-it-qat \
docker compose run --rm --build --service-ports app
```

You can still use `docker compose up --build` for non-interactive log-first
workflows, but `run` is usually better for full-screen terminal apps.

If MCP works but chat fails, verify Ollama is reachable from inside the
container and ensure it is running with `OLLAMA_HOST=0.0.0.0:11434`.

Stop and remove the container:

```bash
docker compose down
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

Both suites run from the **same shared venv**. From the repo root:

```bash
uv run pytest server -q     # server tests (31)
uv run pytest tui    -q     # TUI tests, headless + mocked network (9)
uv run pytest server tui -q # both
```
