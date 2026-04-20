from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from litellm.exceptions import RateLimitError, InternalServerError

from agent_core.agent_service import AgentService


@pytest.fixture(autouse=True)
def _no_litellm_config():
    with patch("agent_core.agent_service.configure_litellm"):
        yield


# Patch sleep globally so retries don't actually wait
@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("agent_core.agent_service.asyncio.sleep", new=AsyncMock()):
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


def _rate_limit():
    return RateLimitError(
        message="rate limit exceeded", llm_provider="openai", model="gpt-4o"
    )


def _internal_error():
    return InternalServerError(
        message="internal server error", llm_provider="openai", model="gpt-4o"
    )


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
    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(side_effect=_rate_limit()),
    ):
        result = await service.invoke("prompt")

    assert "error" in result
    assert "rate limit exceeded" in result["error"]


async def test_invoke_handles_internal_server_error(service):
    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(side_effect=_internal_error()),
    ):
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


# ---------------------------------------------------------------------------
# Retry + backoff tests
# ---------------------------------------------------------------------------


async def test_retry_succeeds_on_second_attempt(service, mock_runner_result):
    """Fails once with RateLimitError, succeeds on the second attempt."""
    run_mock = AsyncMock(side_effect=[_rate_limit(), mock_runner_result])
    with patch("agent_core.agent_service.Runner.run", new=run_mock):
        result = await service.invoke("prompt")

    assert result == {"response": "Here are your recommendations."}
    assert run_mock.await_count == 2


async def test_retry_succeeds_on_third_attempt(service, mock_runner_result):
    run_mock = AsyncMock(
        side_effect=[_rate_limit(), _internal_error(), mock_runner_result]
    )
    with patch("agent_core.agent_service.Runner.run", new=run_mock):
        result = await service.invoke("prompt")

    assert result == {"response": "Here are your recommendations."}
    assert run_mock.await_count == 3


async def test_all_retries_exhausted_returns_error(service):
    """All MAX_RETRIES attempts fail — must return error dict, not raise."""
    with (
        patch("agent_core.agent_service._MAX_RETRIES", 3),
        patch(
            "agent_core.agent_service.Runner.run",
            new=AsyncMock(side_effect=_rate_limit()),
        ) as run_mock,
    ):
        result = await service.invoke("prompt")

    assert "error" in result
    assert run_mock.await_count == 3


async def test_sleep_called_between_retries(service, mock_runner_result):
    """asyncio.sleep must be called (attempt-1) times before success."""
    run_mock = AsyncMock(side_effect=[_rate_limit(), _rate_limit(), mock_runner_result])
    with (
        patch("agent_core.agent_service.Runner.run", new=run_mock),
        patch("agent_core.agent_service.asyncio.sleep", new=AsyncMock()) as sleep_mock,
    ):
        await service.invoke("prompt")

    assert sleep_mock.await_count == 2


async def test_sleep_not_called_on_first_success(service, mock_runner_result):
    with (
        patch(
            "agent_core.agent_service.Runner.run",
            new=AsyncMock(return_value=mock_runner_result),
        ),
        patch("agent_core.agent_service.asyncio.sleep", new=AsyncMock()) as sleep_mock,
    ):
        await service.invoke("prompt")

    sleep_mock.assert_not_awaited()


async def test_sleep_not_called_after_last_failed_attempt(service):
    """No sleep after the final attempt — no point waiting before returning."""
    with (
        patch("agent_core.agent_service._MAX_RETRIES", 2),
        patch(
            "agent_core.agent_service.Runner.run",
            new=AsyncMock(side_effect=_rate_limit()),
        ),
        patch("agent_core.agent_service.asyncio.sleep", new=AsyncMock()) as sleep_mock,
    ):
        await service.invoke("prompt")

    # 2 attempts → sleep only between attempt 1 and 2 → 1 sleep call
    assert sleep_mock.await_count == 1


async def test_non_retryable_exception_propagates(service):
    """Exceptions that are not RateLimitError / InternalServerError must propagate."""
    with patch(
        "agent_core.agent_service.Runner.run",
        new=AsyncMock(side_effect=ValueError("bad prompt")),
    ):
        with pytest.raises(ValueError, match="bad prompt"):
            await service.invoke("prompt")


async def test_backoff_delay_increases_with_attempt():
    """Each successive delay must be strictly larger (ignoring jitter)."""
    from agent_core.agent_service import _backoff_delay

    # Use zero jitter (patch random.uniform) to get deterministic values
    with patch("agent_core.agent_service.random.uniform", return_value=0):
        delays = [_backoff_delay(i) for i in range(4)]

    for i in range(len(delays) - 1):
        assert (
            delays[i] < delays[i + 1]
        ), f"delay[{i}]={delays[i]} should be < delay[{i+1}]={delays[i+1]}"


async def test_backoff_delay_capped_at_max():
    """Delay must never exceed _BACKOFF_MAX + 1 (jitter ceiling)."""
    from agent_core.agent_service import _backoff_delay, _BACKOFF_MAX

    with patch("agent_core.agent_service.random.uniform", return_value=1.0):
        delay = _backoff_delay(100)  # very large attempt

    assert delay <= _BACKOFF_MAX + 1.0
