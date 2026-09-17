import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

import indexer
import tools  # noqa: F401  (registers the MCP tools)
from mcp_server import mcp

logger = logging.getLogger(__name__)


async def _build_index() -> None:
    try:
        await asyncio.to_thread(indexer.rag_index.build)
    except Exception:
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
    return {"status": "healthy"}

app.mount("/", mcp.streamable_http_app())