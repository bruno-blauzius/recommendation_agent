from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.agent_with_mcp import agent_with_mcp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mcp_server():
    """Return a MagicMock that behaves as an async context manager."""
    server = MagicMock()
    server.__aenter__ = AsyncMock(return_value=server)
    server.__aexit__ = AsyncMock(return_value=False)
    return server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_mcp_server():
    return _make_mcp_server()


@pytest.fixture
def mock_agent_openai():
    adapter = MagicMock()
    adapter.create_agent.return_value = MagicMock()
    return adapter


@pytest.fixture
def mock_agent_service():
    service = MagicMock()
    service.invoke = AsyncMock(return_value={"response": "ok"})
    return service


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_invoke_is_called_with_prompt(
    mock_mcp_server, mock_agent_openai, mock_agent_service
):
    """agent_with_mcp must forward the prompt to AgentService.invoke."""
    prompt = "What restaurants are in NYC?"

    with (
        patch("services.agent_with_mcp.MCPServerStdio", return_value=mock_mcp_server),
        patch("services.agent_with_mcp.AgentOpenAI", return_value=mock_agent_openai),
        patch("services.agent_with_mcp.AgentService", return_value=mock_agent_service),
    ):

        await agent_with_mcp(prompt)

    mock_agent_service.invoke.assert_awaited_once()
    call_kwargs = mock_agent_service.invoke.call_args
    assert call_kwargs.kwargs["prompt"] == prompt


async def test_mcp_server_is_passed_to_invoke(
    mock_mcp_server, mock_agent_openai, mock_agent_service
):
    """The files_server returned by MCPServerStdio must be passed as mcp_servers."""
    with (
        patch("services.agent_with_mcp.MCPServerStdio", return_value=mock_mcp_server),
        patch("services.agent_with_mcp.AgentOpenAI", return_value=mock_agent_openai),
        patch("services.agent_with_mcp.AgentService", return_value=mock_agent_service),
    ):

        await agent_with_mcp("prompt")

    call_kwargs = mock_agent_service.invoke.call_args
    assert call_kwargs.kwargs["mcp_servers"] == [mock_mcp_server]


async def test_agent_openai_created_with_correct_name_and_model(
    mock_mcp_server, mock_agent_service
):
    """AgentOpenAI must be instantiated with name='recommendation_agent'
    and model_name='gpt-4o-mini'."""
    with (
        patch("services.agent_with_mcp.MCPServerStdio", return_value=mock_mcp_server),
        patch("services.agent_with_mcp.AgentOpenAI") as mock_cls,
        patch("services.agent_with_mcp.AgentService", return_value=mock_agent_service),
    ):

        mock_cls.return_value = MagicMock()
        await agent_with_mcp("prompt")

    mock_cls.assert_called_once_with(
        name="recommendation_agent", model_name="gpt-4o-mini"
    )


async def test_mcp_server_stdio_created_with_filesystem_params(
    mock_agent_openai, mock_agent_service
):
    """MCPServerStdio must use npx + @modelcontextprotocol/server-filesystem."""
    with (
        patch("services.agent_with_mcp.MCPServerStdio") as mock_stdio_cls,
        patch("services.agent_with_mcp.AgentOpenAI", return_value=mock_agent_openai),
        patch("services.agent_with_mcp.AgentService", return_value=mock_agent_service),
    ):

        mcp_instance = _make_mcp_server()
        mock_stdio_cls.return_value = mcp_instance

        await agent_with_mcp("prompt")

    _, kwargs = mock_stdio_cls.call_args
    params = (
        kwargs.get("params") or mock_stdio_cls.call_args.args[0]
        if mock_stdio_cls.call_args.args
        else kwargs["params"]
    )
    assert params["command"] == "npx"
    assert "@modelcontextprotocol/server-filesystem" in params["args"]


async def test_agent_service_constructed_with_adapter(
    mock_mcp_server, mock_agent_openai
):
    """AgentService must receive the AgentOpenAI instance as model_adapter."""
    with (
        patch("services.agent_with_mcp.MCPServerStdio", return_value=mock_mcp_server),
        patch("services.agent_with_mcp.AgentOpenAI", return_value=mock_agent_openai),
        patch("services.agent_with_mcp.AgentService") as mock_service_cls,
    ):

        service_instance = MagicMock()
        service_instance.invoke = AsyncMock(return_value={"response": "ok"})
        mock_service_cls.return_value = service_instance

        await agent_with_mcp("prompt")

    mock_service_cls.assert_called_once_with(model_adapter=mock_agent_openai)


async def test_exception_from_invoke_propagates(mock_mcp_server, mock_agent_openai):
    """Exceptions raised by AgentService.invoke must propagate to the caller."""
    broken_service = MagicMock()
    broken_service.invoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with (
        patch("services.agent_with_mcp.MCPServerStdio", return_value=mock_mcp_server),
        patch("services.agent_with_mcp.AgentOpenAI", return_value=mock_agent_openai),
        patch("services.agent_with_mcp.AgentService", return_value=broken_service),
    ):

        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await agent_with_mcp("prompt")


async def test_mcp_context_manager_entered(mock_agent_openai, mock_agent_service):
    """MCPServerStdio must be used as an async context manager (__aenter__ called)."""
    mcp_server = _make_mcp_server()

    with (
        patch("services.agent_with_mcp.MCPServerStdio", return_value=mcp_server),
        patch("services.agent_with_mcp.AgentOpenAI", return_value=mock_agent_openai),
        patch("services.agent_with_mcp.AgentService", return_value=mock_agent_service),
    ):

        await agent_with_mcp("prompt")

    mcp_server.__aenter__.assert_awaited_once()


async def test_mcp_context_manager_exited(mock_agent_openai, mock_agent_service):
    """MCPServerStdio.__aexit__ must be called even when invoke succeeds."""
    mcp_server = _make_mcp_server()

    with (
        patch("services.agent_with_mcp.MCPServerStdio", return_value=mcp_server),
        patch("services.agent_with_mcp.AgentOpenAI", return_value=mock_agent_openai),
        patch("services.agent_with_mcp.AgentService", return_value=mock_agent_service),
    ):

        await agent_with_mcp("prompt")

    mcp_server.__aexit__.assert_awaited_once()
