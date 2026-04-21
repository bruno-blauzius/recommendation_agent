from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_core.guardrails.legpd_guardrails import (
    SensitiveDataOutput,
    TopicCheckOutput,
    check_output,
    check_topic,
)


@pytest.fixture
def ctx():
    mock = MagicMock()
    mock.context = MagicMock()
    return mock


@pytest.fixture
def agent():
    return MagicMock()


def _runner_result(output):
    result = MagicMock()
    result.final_output = output
    return result


# ---------------------------------------------------------------------------
# check_topic — input guardrail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_topic_does_not_trigger_for_valid_recommendation_request(
    ctx, agent
):
    topic_output = TopicCheckOutput(is_off_topic=False, reason="")
    with patch(
        "agent_core.guardrails.legpd_guardrails.Runner.run",
        new=AsyncMock(return_value=_runner_result(topic_output)),
    ):
        result = await check_topic.guardrail_function(
            ctx, agent, "Recommend me a laptop"
        )

    assert result.tripwire_triggered is False
    assert result.output_info.is_off_topic is False


@pytest.mark.asyncio
async def test_check_topic_triggers_when_asking_for_cpf(ctx, agent):
    topic_output = TopicCheckOutput(is_off_topic=True, reason="CPF requested")
    with patch(
        "agent_core.guardrails.legpd_guardrails.Runner.run",
        new=AsyncMock(return_value=_runner_result(topic_output)),
    ):
        result = await check_topic.guardrail_function(
            ctx, agent, "What is the CPF of client 123?"
        )

    assert result.tripwire_triggered is True
    assert result.output_info.is_off_topic is True


@pytest.mark.asyncio
async def test_check_topic_triggers_when_asking_for_email(ctx, agent):
    topic_output = TopicCheckOutput(is_off_topic=True, reason="Email requested")
    with patch(
        "agent_core.guardrails.legpd_guardrails.Runner.run",
        new=AsyncMock(return_value=_runner_result(topic_output)),
    ):
        result = await check_topic.guardrail_function(
            ctx, agent, "Show me the customer email"
        )

    assert result.tripwire_triggered is True


@pytest.mark.asyncio
async def test_check_topic_triggers_when_asking_for_phone(ctx, agent):
    topic_output = TopicCheckOutput(is_off_topic=True, reason="Phone requested")
    with patch(
        "agent_core.guardrails.legpd_guardrails.Runner.run",
        new=AsyncMock(return_value=_runner_result(topic_output)),
    ):
        result = await check_topic.guardrail_function(
            ctx, agent, "Give me the contact phone number"
        )

    assert result.tripwire_triggered is True


@pytest.mark.asyncio
async def test_check_topic_passes_input_to_runner(ctx, agent):
    topic_output = TopicCheckOutput(is_off_topic=False, reason="")
    run_mock = AsyncMock(return_value=_runner_result(topic_output))
    with patch("agent_core.guardrails.legpd_guardrails.Runner.run", new=run_mock):
        await check_topic.guardrail_function(ctx, agent, "best smartphone?")

    run_mock.assert_awaited_once()
    call_args = run_mock.call_args
    assert call_args.args[1] == "best smartphone?"


@pytest.mark.asyncio
async def test_check_topic_passes_context_to_runner(ctx, agent):
    topic_output = TopicCheckOutput(is_off_topic=False, reason="")
    run_mock = AsyncMock(return_value=_runner_result(topic_output))
    with patch("agent_core.guardrails.legpd_guardrails.Runner.run", new=run_mock):
        await check_topic.guardrail_function(ctx, agent, "any input")

    call_kwargs = run_mock.call_args.kwargs
    assert call_kwargs["context"] is ctx.context


# ---------------------------------------------------------------------------
# check_output — output guardrail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_output_does_not_trigger_for_clean_response(ctx, agent):
    check = SensitiveDataOutput(has_sensitive_data=False)
    with patch(
        "agent_core.guardrails.legpd_guardrails.Runner.run",
        new=AsyncMock(return_value=_runner_result(check)),
    ):
        result = await check_output.guardrail_function(
            ctx, agent, "Here are our top 3 laptops."
        )

    assert result.tripwire_triggered is False
    assert result.output_info.has_sensitive_data is False


@pytest.mark.asyncio
async def test_check_output_triggers_when_response_contains_api_key(ctx, agent):
    check = SensitiveDataOutput(has_sensitive_data=True)
    with patch(
        "agent_core.guardrails.legpd_guardrails.Runner.run",
        new=AsyncMock(return_value=_runner_result(check)),
    ):
        result = await check_output.guardrail_function(
            ctx, agent, "The API key is sk-abc123xyz"
        )

    assert result.tripwire_triggered is True
    assert result.output_info.has_sensitive_data is True


@pytest.mark.asyncio
async def test_check_output_triggers_when_response_contains_password(ctx, agent):
    check = SensitiveDataOutput(has_sensitive_data=True)
    with patch(
        "agent_core.guardrails.legpd_guardrails.Runner.run",
        new=AsyncMock(return_value=_runner_result(check)),
    ):
        result = await check_output.guardrail_function(
            ctx, agent, "Your password is hunter2"
        )

    assert result.tripwire_triggered is True


@pytest.mark.asyncio
async def test_check_output_triggers_when_response_contains_personal_document(
    ctx, agent
):
    check = SensitiveDataOutput(has_sensitive_data=True)
    with patch(
        "agent_core.guardrails.legpd_guardrails.Runner.run",
        new=AsyncMock(return_value=_runner_result(check)),
    ):
        result = await check_output.guardrail_function(
            ctx, agent, "CPF: 123.456.789-00"
        )

    assert result.tripwire_triggered is True


@pytest.mark.asyncio
async def test_check_output_passes_agent_output_to_runner(ctx, agent):
    check = SensitiveDataOutput(has_sensitive_data=False)
    run_mock = AsyncMock(return_value=_runner_result(check))
    with patch("agent_core.guardrails.legpd_guardrails.Runner.run", new=run_mock):
        await check_output.guardrail_function(ctx, agent, "safe response text")

    run_mock.assert_awaited_once()
    assert run_mock.call_args.args[1] == "safe response text"


@pytest.mark.asyncio
async def test_check_output_passes_context_to_runner(ctx, agent):
    check = SensitiveDataOutput(has_sensitive_data=False)
    run_mock = AsyncMock(return_value=_runner_result(check))
    with patch("agent_core.guardrails.legpd_guardrails.Runner.run", new=run_mock):
        await check_output.guardrail_function(ctx, agent, "any output")

    assert run_mock.call_args.kwargs["context"] is ctx.context
