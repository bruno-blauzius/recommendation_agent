from unittest.mock import MagicMock, patch

import pytest

from agent_core.agents_anthropic import AgentClaude

INSTRUCTIONS = "You are a helpful assistant."


@pytest.fixture
def claude_adapter():
    with patch("agent_core.agent_adapter.load_instructions", return_value=INSTRUCTIONS):
        with patch("agent_core.agents_anthropic.LitellmModel") as MockLitellm:
            MockLitellm.return_value = MagicMock(name="litellm_model_instance")
            adapter = AgentClaude(name="default", model_name="claude-3-5-sonnet")
            yield adapter


def test_init_stores_name_and_model_name(claude_adapter):
    assert claude_adapter.name == "default"
    assert claude_adapter.model_name == "claude-3-5-sonnet"


def test_init_stores_instructions(claude_adapter):
    assert claude_adapter.instructions == INSTRUCTIONS


def test_init_wraps_model_in_litellm_model():
    with patch("agent_core.agent_adapter.load_instructions", return_value=INSTRUCTIONS):
        with patch("agent_core.agents_anthropic.LitellmModel") as MockLitellm:
            mock_instance = MagicMock()
            MockLitellm.return_value = mock_instance
            adapter = AgentClaude(name="default", model_name="claude-3-5-sonnet")

    MockLitellm.assert_called_once_with(model="claude-3-5-sonnet")
    assert adapter._litellm_model is mock_instance


def test_init_raises_when_instructions_not_found():
    with patch("agent_core.agent_adapter.load_instructions", return_value=""):
        with patch("agent_core.agents_anthropic.LitellmModel"):
            with pytest.raises(
                ValueError, match="No instructions found for agent 'unknown'"
            ):
                AgentClaude(name="unknown", model_name="claude-3-5-sonnet")


def test_create_agent_returns_agent_instance(claude_adapter):
    mock_agent = MagicMock()
    with patch(
        "agent_core.agents_anthropic.Agent", return_value=mock_agent
    ) as MockAgent:
        result = claude_adapter.create_agent()

    MockAgent.assert_called_once_with(
        name="default",
        model=claude_adapter._litellm_model,
        instructions=INSTRUCTIONS,
        mcp_servers=[],
        input_guardrails=[],
        output_guardrails=[],
    )
    assert result is mock_agent


def test_create_agent_uses_litellm_model_not_raw_string(claude_adapter):
    with patch("agent_core.agents_anthropic.Agent") as MockAgent:
        claude_adapter.create_agent()

    passed_model = MockAgent.call_args.kwargs["model"]
    assert passed_model is claude_adapter._litellm_model
    assert passed_model is not claude_adapter.model_name


def test_create_agent_passes_mcp_servers(claude_adapter):
    mcp_mock = MagicMock()
    with patch("agent_core.agents_anthropic.Agent") as MockAgent:
        claude_adapter.create_agent(mcp_servers=[mcp_mock])

    assert MockAgent.call_args.kwargs["mcp_servers"] == [mcp_mock]


def test_create_agent_passes_input_guardrails(claude_adapter):
    guardrail_mock = MagicMock()
    with patch("agent_core.agents_anthropic.Agent") as MockAgent:
        claude_adapter.create_agent(input_guardrails=[guardrail_mock])

    assert MockAgent.call_args.kwargs["input_guardrails"] == [guardrail_mock]


def test_create_agent_defaults_to_empty_lists_when_none(claude_adapter):
    with patch("agent_core.agents_anthropic.Agent") as MockAgent:
        claude_adapter.create_agent(
            mcp_servers=None, input_guardrails=None, output_guardrails=None
        )

    call_kwargs = MockAgent.call_args.kwargs
    assert call_kwargs["mcp_servers"] == []
    assert call_kwargs["input_guardrails"] == []
    assert call_kwargs["output_guardrails"] == []


def test_create_agent_raises_runtime_error_on_sdk_failure(claude_adapter):
    with patch(
        "agent_core.agents_anthropic.Agent", side_effect=Exception("LiteLLM error")
    ):
        with pytest.raises(
            RuntimeError, match="Failed to create Claude agent: LiteLLM error"
        ):
            claude_adapter.create_agent()
