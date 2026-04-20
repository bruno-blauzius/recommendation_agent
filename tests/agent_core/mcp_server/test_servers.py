import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import agent_core.mcp_server.servers as _module
from agent_core.mcp_server.servers import _get_mcp_file_server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mcp_server() -> MagicMock:
    server = MagicMock()
    server.__aenter__ = AsyncMock(return_value=server)
    server.__aexit__ = AsyncMock(return_value=False)
    return server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure a clean singleton state before and after every test."""
    _module._mcp_server = None
    _module._mcp_lock = None
    yield
    _module._mcp_server = None
    _module._mcp_lock = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_call_creates_server():
    """On first call the MCPServerStdio must be instantiated and entered."""
    mcp_instance = _make_mcp_server()

    with patch(
        "agent_core.mcp_server.servers.MCPServerStdio", return_value=mcp_instance
    ) as mock_cls:
        result = await _get_mcp_file_server()

    mock_cls.assert_called_once()
    mcp_instance.__aenter__.assert_awaited_once()
    assert result is mcp_instance


@pytest.mark.asyncio
async def test_second_call_returns_same_instance():
    """Subsequent calls must return the cached singleton without spawning again."""
    mcp_instance = _make_mcp_server()

    with patch(
        "agent_core.mcp_server.servers.MCPServerStdio", return_value=mcp_instance
    ) as mock_cls:
        first = await _get_mcp_file_server()
        second = await _get_mcp_file_server()

    assert first is second
    mock_cls.assert_called_once()
    mcp_instance.__aenter__.assert_awaited_once()


@pytest.mark.asyncio
async def test_server_created_with_filesystem_params():
    """MCPServerStdio must be configured with npx + server-filesystem."""
    mcp_instance = _make_mcp_server()

    with patch(
        "agent_core.mcp_server.servers.MCPServerStdio", return_value=mcp_instance
    ) as mock_cls:
        await _get_mcp_file_server()

    call_kwargs = mock_cls.call_args.kwargs
    params = call_kwargs.get("params") or mock_cls.call_args.args[0]
    assert params["command"] == "npx"
    assert "@modelcontextprotocol/server-filesystem" in params["args"]


@pytest.mark.asyncio
async def test_server_has_session_timeout():
    """MCPServerStdio must be configured with a client_session_timeout_seconds."""
    mcp_instance = _make_mcp_server()

    with patch(
        "agent_core.mcp_server.servers.MCPServerStdio", return_value=mcp_instance
    ) as mock_cls:
        await _get_mcp_file_server()

    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs.get("client_session_timeout_seconds") is not None
    assert call_kwargs["client_session_timeout_seconds"] > 0


@pytest.mark.asyncio
async def test_concurrent_calls_create_only_one_server():
    """Concurrent invocations must not race and spawn multiple servers."""
    mcp_instance = _make_mcp_server()
    call_count = 0

    def _counting_factory(**kwargs):
        nonlocal call_count
        call_count += 1
        return mcp_instance

    with patch(
        "agent_core.mcp_server.servers.MCPServerStdio", side_effect=_counting_factory
    ):
        results = await asyncio.gather(
            _get_mcp_file_server(),
            _get_mcp_file_server(),
            _get_mcp_file_server(),
        )

    assert call_count == 1
    assert all(r is mcp_instance for r in results)


@pytest.mark.asyncio
async def test_singleton_stored_in_module_state():
    """After first call, the singleton must be stored in the module-level variable."""
    mcp_instance = _make_mcp_server()

    with patch(
        "agent_core.mcp_server.servers.MCPServerStdio", return_value=mcp_instance
    ):
        await _get_mcp_file_server()

    assert _module._mcp_server is mcp_instance


@pytest.mark.asyncio
async def test_lock_initialised_on_first_call():
    """The asyncio.Lock must be initialised during the first call."""
    mcp_instance = _make_mcp_server()

    assert _module._mcp_lock is None

    with patch(
        "agent_core.mcp_server.servers.MCPServerStdio", return_value=mcp_instance
    ):
        await _get_mcp_file_server()

    assert _module._mcp_lock is not None
    assert isinstance(_module._mcp_lock, asyncio.Lock)
