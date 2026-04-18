from unittest.mock import MagicMock

import pytest

from agent_core.guardrails.pii_guardrail import pii_guardrail


@pytest.fixture
def ctx():
    return MagicMock()


@pytest.fixture
def agent():
    return MagicMock()


async def test_clean_prompt_does_not_trigger_guardrail(ctx, agent):
    result = await pii_guardrail.guardrail_function(
        ctx, agent, "What products do you recommend?"
    )

    assert result.tripwire_triggered is False
    assert result.output_info["pii_detected"] is False


async def test_email_triggers_guardrail(ctx, agent):
    result = await pii_guardrail.guardrail_function(
        ctx, agent, "Contact me at user@example.com"
    )

    assert result.tripwire_triggered is True
    assert result.output_info["pii_detected"] is True


async def test_cpf_triggers_guardrail(ctx, agent):
    result = await pii_guardrail.guardrail_function(ctx, agent, "My CPF is 12345678901")

    assert result.tripwire_triggered is True
    assert result.output_info["pii_detected"] is True


async def test_card_number_triggers_guardrail(ctx, agent):
    result = await pii_guardrail.guardrail_function(
        ctx, agent, "Card: 1234567890123456"
    )

    assert result.tripwire_triggered is True
    assert result.output_info["pii_detected"] is True


async def test_short_number_does_not_trigger_guardrail(ctx, agent):
    result = await pii_guardrail.guardrail_function(ctx, agent, "I want 5 items please")

    assert result.tripwire_triggered is False
    assert result.output_info["pii_detected"] is False


async def test_both_email_and_cpf_trigger_guardrail(ctx, agent):
    result = await pii_guardrail.guardrail_function(
        ctx, agent, "Email: test@test.com, CPF: 98765432100"
    )

    assert result.tripwire_triggered is True
    assert result.output_info["pii_detected"] is True


async def test_number_below_min_length_does_not_trigger(ctx, agent):
    result = await pii_guardrail.guardrail_function(ctx, agent, "Code 1234567890")

    assert result.tripwire_triggered is False


async def test_number_above_max_length_does_not_trigger(ctx, agent):
    result = await pii_guardrail.guardrail_function(
        ctx, agent, "Code 12345678901234567"
    )

    assert result.tripwire_triggered is False


async def test_empty_prompt_does_not_trigger_guardrail(ctx, agent):
    result = await pii_guardrail.guardrail_function(ctx, agent, "")

    assert result.tripwire_triggered is False
    assert result.output_info["pii_detected"] is False
