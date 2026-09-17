from typing import TypedDict

from mcp.server.mcpserver.exceptions import ToolError

import indexer
from mcp_server import mcp
from tools import common


class RagMatch(TypedDict):
    file: str
    text: str
    score: float


@mcp.tool()
async def rag_query(query_text: str) -> list[RagMatch]:
    """Run a text query across the vault using RAG."""
    return _rag_query(query_text)


@common.tool_generic_error_handler()
def _rag_query(query_text: str) -> list[RagMatch]:
    if not indexer.rag_index.ready:
        raise ToolError("503 Service Unavailable")
    return indexer.rag_index.query(query_text)


@mcp.tool()
async def rag_flush_index() -> int:
    """Flush the RAG index and trigger a full reindex."""
    return _rag_flush_index()


@common.tool_generic_error_handler()
def _rag_flush_index() -> int:
    indexer.rag_index.flush()
    indexer.rag_index.build()
    return 200