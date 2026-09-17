from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

import tools  # noqa: F401  (registers the MCP tools)
from mcp_server import mcp


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Obsidian MCP Server", lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Welcome to the Obsidian MCP Server"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

app.mount("/", mcp.streamable_http_app())