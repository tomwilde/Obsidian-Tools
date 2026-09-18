#!/usr/bin/env bash
set -euo pipefail

MCP_HOST="${MCP_HOST:-0.0.0.0}"
MCP_PORT="${MCP_PORT:-8000}"
MCP_URL="${MCP_URL:-http://127.0.0.1:${MCP_PORT}/mcp}"
OLLAMA_URL="${OLLAMA_URL:-http://host.docker.internal:11434/v1}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:12b-it-qat}"
export VAULT_DIR="${VAULT_DIR:-/data/Vault}"

if [[ ! -d "${VAULT_DIR}" ]]; then
  echo "[warn] VAULT_DIR does not exist: ${VAULT_DIR}" >&2
fi

cleanup() {
  if [[ -n "${server_pid:-}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "[boot] Starting MCP server on ${MCP_HOST}:${MCP_PORT}"
(
  cd /app/server
  uv run uvicorn main:app --app-dir src --host "${MCP_HOST}" --port "${MCP_PORT}"
) &
server_pid=$!

echo "[boot] Waiting for server health..."
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${MCP_PORT}/health" >/dev/null; then
    break
  fi
  sleep 0.5
done

if ! curl -fsS "http://127.0.0.1:${MCP_PORT}/health" >/dev/null; then
  echo "[error] MCP server failed to become healthy" >&2
  exit 1
fi

echo "[boot] Launching TUI (model=${OLLAMA_MODEL})"
set +e
cd /app/tui
uv run python src/main.py \
  --mcp-url "${MCP_URL}" \
  --ollama-url "${OLLAMA_URL}" \
  --model "${OLLAMA_MODEL}" \
  "$@"
tui_status=$?
set -e

exit "${tui_status}"
