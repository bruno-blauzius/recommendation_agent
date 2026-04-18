from unittest.mock import MagicMock, patch

import pytest

from agent_core.agent_openai import AgentOpenAI

INSTRUCTIONS = "You are a helpful assistant."


@pytest.fixture
def openai_adapter():
    with patch("agent_core.agent_adapter.load_instructions", return_value=INSTRUCTIONS):
        yield AgentOpenAI(name="default", model_name="gpt-4o")


def test_init_stores_name_and_model(openai_adapter):
    assert openai_adapter.name == "default"
    assert openai_adapter.model_name == "gpt-4o"


def test_init_stores_instructions(openai_adapter):
    assert openai_adapter.instructions == INSTRUCTIONS


def test_init_raises_when_instructions_not_found():
    with patch("agent_core.agent_adapter.load_instructions", return_value=""):
        with pytest.raises(
            ValueError, match="No instructions found for agent 'unknown'"
        ):
            AgentOpenAI(name="unknown", model_name="gpt-4o")


def test_create_agent_returns_agent_instance(openai_adapter):
    mock_agent = MagicMock()
    with patch("agent_core.agent_openai.Agent", return_value=mock_agent) as MockAgent:
        result = openai_adapter.create_agent()

    MockAgent.assert_called_once_with(
        name="default",
        model="gpt-4o",
        instructions=INSTRUCTIONS,
        mcp_servers=[],
        input_guardrails=[],
        output_guardrails=[],
    )
    assert result is mock_agent


def test_create_agent_passes_mcp_servers(openai_adapter):
    mcp_mock = MagicMock()
    with patch("agent_core.agent_openai.Agent") as MockAgent:
        openai_adapter.create_agent(mcp_servers=[mcp_mock])

    assert MockAgent.call_args.kwargs["mcp_servers"] == [mcp_mock]


def test_create_agent_passes_input_guardrails(openai_adapter):
    guardrail_mock = MagicMock()
    with patch("agent_core.agent_openai.Agent") as MockAgent:
        openai_adapter.create_agent(input_guardrails=[guardrail_mock])

    assert MockAgent.call_args.kwargs["input_guardrails"] == [guardrail_mock]


def test_create_agent_passes_output_guardrails(openai_adapter):
    guardrail_mock = MagicMock()
    with patch("agent_core.agent_openai.Agent") as MockAgent:
        openai_adapter.create_agent(output_guardrails=[guardrail_mock])

    assert MockAgent.call_args.kwargs["output_guardrails"] == [guardrail_mock]


def test_create_agent_defaults_to_empty_lists_when_none(openai_adapter):
    with patch("agent_core.agent_openai.Agent") as MockAgent:
        openai_adapter.create_agent(
            mcp_servers=None, input_guardrails=None, output_guardrails=None
        )

    call_kwargs = MockAgent.call_args.kwargs
    assert call_kwargs["mcp_servers"] == []
    assert call_kwargs["input_guardrails"] == []
    assert call_kwargs["output_guardrails"] == []


def test_create_agent_raises_runtime_error_on_sdk_failure(openai_adapter):
    with patch("agent_core.agent_openai.Agent", side_effect=Exception("SDK error")):
        with pytest.raises(
            RuntimeError, match="Failed to create OpenAI agent: SDK error"
        ):
            openai_adapter.create_agent()
