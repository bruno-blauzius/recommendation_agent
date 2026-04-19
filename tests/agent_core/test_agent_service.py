from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_core.agent_service import AgentService


@pytest.fixture(autouse=True)
def _no_litellm_config():
    with patch("agent_core.agent_service.configure_litellm"):
        yield


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    adapter.create_agent.return_value = MagicMock()
    return adapter


@pytest.fixture
def service(mock_adapter):
    return AgentService(model_adapter=mock_adapter)


@pytest.fixture
def mock_runner_result():
    result = MagicMock()
    result.final_output = "Here are your recommendations."
    return result


async def test_invoke_returns_response_on_success(service, mock_runner_result):
    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(return_value=mock_runner_result),
    ):
        result = await service.invoke("What should I buy?")

    assert result == {"response": "Here are your recommendations."}


async def test_invoke_calls_create_agent_with_defaults(
    service, mock_adapter, mock_runner_result
):
    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(return_value=mock_runner_result),
    ):
        await service.invoke("recommend me something")

    mock_adapter.create_agent.assert_called_once_with(
        mcp_servers=[],
        input_guardrails=None,
        output_guardrails=None,
    )


async def test_invoke_passes_input_guardrails_to_create_agent(
    service, mock_adapter, mock_runner_result
):
    guardrail = MagicMock()
    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(return_value=mock_runner_result),
    ):
        await service.invoke("prompt", input_guardrails=[guardrail])

    mock_adapter.create_agent.assert_called_once_with(
        mcp_servers=[],
        input_guardrails=[guardrail],
        output_guardrails=None,
    )


async def test_invoke_passes_output_guardrails_to_create_agent(
    service, mock_adapter, mock_runner_result
):
    guardrail = MagicMock()
    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(return_value=mock_runner_result),
    ):
        await service.invoke("prompt", output_guardrails=[guardrail])

    mock_adapter.create_agent.assert_called_once_with(
        mcp_servers=[],
        input_guardrails=None,
        output_guardrails=[guardrail],
    )


async def test_invoke_enters_and_exits_mcp_context(service, mock_runner_result):
    mcp = AsyncMock()
    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(return_value=mock_runner_result),
    ):
        await service.invoke("prompt", mcp_servers=[mcp])

    mcp.__aenter__.assert_called_once()
    mcp.__aexit__.assert_called_once()


async def test_invoke_passes_mcp_servers_to_create_agent(
    service, mock_adapter, mock_runner_result
):
    mcp = AsyncMock()
    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(return_value=mock_runner_result),
    ):
        await service.invoke("prompt", mcp_servers=[mcp])

    call_kwargs = mock_adapter.create_agent.call_args.kwargs
    assert call_kwargs["mcp_servers"] == [mcp]


async def test_invoke_calls_runner_run_with_agent_and_prompt(
    service, mock_adapter, mock_runner_result
):
    mock_agent = MagicMock()
    mock_adapter.create_agent.return_value = mock_agent

    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(return_value=mock_runner_result),
    ) as mock_run:
        await service.invoke("my prompt")

    mock_run.assert_called_once_with(mock_agent, input="my prompt")


async def test_invoke_handles_rate_limit_error(service):
    from litellm.exceptions import RateLimitError

    error = RateLimitError(
        message="rate limit exceeded", llm_provider="openai", model="gpt-4o"
    )
    with patch("agent_core.agent_service.Runner.run", new=AsyncMock(side_effect=error)):
        result = await service.invoke("prompt")

    assert "error" in result
    assert "rate limit exceeded" in result["error"]


async def test_invoke_handles_internal_server_error(service):
    from litellm.exceptions import InternalServerError

    error = InternalServerError(
        message="internal server error", llm_provider="openai", model="gpt-4o"
    )
    with patch("agent_core.agent_service.Runner.run", new=AsyncMock(side_effect=error)):
        result = await service.invoke("prompt")

    assert "error" in result
    assert "internal server error" in result["error"]


async def test_invoke_with_none_mcp_uses_empty_list(
    service, mock_adapter, mock_runner_result
):
    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(return_value=mock_runner_result),
    ):
        await service.invoke("prompt", mcp_servers=None)

    call_kwargs = mock_adapter.create_agent.call_args.kwargs
    assert call_kwargs["mcp_servers"] == []
