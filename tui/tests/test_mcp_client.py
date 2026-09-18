import asyncio

import pytest

from mcp_client import McpClient


class _Dummy:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.closed = False

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True
        if self.error is not None:
            raise self.error


@pytest.mark.parametrize(
    "message",
    [
        "Session termination failed: 404",
        "oops\nSession termination failed: 404",
    ],
)
def test_aexit_suppresses_session_404(message):
    async def _run():
        client = McpClient("http://localhost:8000/mcp")
        session = _Dummy(RuntimeError(message))
        transport = _Dummy()
        client._session = session
        client._transport = transport

        await client.__aexit__(None, None, None)

        assert session.closed is True
        assert transport.closed is True
        assert client._session is None
        assert client._transport is None

    asyncio.run(_run())


def test_aexit_raises_non_404_session_error():
    async def _run():
        client = McpClient("http://localhost:8000/mcp")
        session = _Dummy(RuntimeError("boom"))
        transport = _Dummy()
        client._session = session
        client._transport = transport

        with pytest.raises(RuntimeError, match="boom"):
            await client.__aexit__(None, None, None)

        assert session.closed is True
        assert transport.closed is True

    asyncio.run(_run())


def test_aexit_raises_transport_error_when_no_session_error():
    async def _run():
        client = McpClient("http://localhost:8000/mcp")
        session = _Dummy()
        transport = _Dummy(RuntimeError("transport failed"))
        client._session = session
        client._transport = transport

        with pytest.raises(RuntimeError, match="transport failed"):
            await client.__aexit__(None, None, None)

        assert session.closed is True
        assert transport.closed is True

    asyncio.run(_run())
