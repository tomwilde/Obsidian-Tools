import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

import indexer
import tools  # noqa: F401  (registers the MCP tools)
from mcp_server import mcp

logger = logging.getLogger(__name__)


def _transport_security_settings() -> TransportSecuritySettings:
    default_hosts = "127.0.0.1:*,localhost:*,[::1]:*,server:*"
    default_origins = "http://127.0.0.1:*,http://localhost:*,http://[::1]:*,http://server:*"
    allowed_hosts = [
        entry.strip()
        for entry in os.environ.get("MCP_ALLOWED_HOSTS", default_hosts).split(",")
        if entry.strip()
    ]
    allowed_origins = [
        entry.strip()
        for entry in os.environ.get("MCP_ALLOWED_ORIGINS", default_origins).split(",")
        if entry.strip()
    ]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


async def _build_index() -> None:
    try:
        rag_status = indexer.rag_index.status
        logger.info(
            "RAG config: mode=%s workers=%s filetypes=%s root=%s",
            rag_status.get("chunking_mode"),
            rag_status.get("index_workers"),
            rag_status.get("included_filetypes"),
            rag_status.get("rootdir"),
        )
        await asyncio.to_thread(indexer.rag_index.build)
    except Exception as exc:
        indexer.rag_index.set_error(exc)
        logger.exception("Failed to build the RAG index")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        task = asyncio.create_task(_build_index())
        try:
            yield
        finally:
            task.cancel()


app = FastAPI(title="Obsidian MCP Server", lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Welcome to the Obsidian MCP Server"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "rag": indexer.rag_index.status,
    }

app.mount(
    "/",
    mcp.streamable_http_app(
        transport_security=_transport_security_settings(),
        host="0.0.0.0",
    ),
)
