from unittest.mock import mock_open, patch

from agent_core.instructions import load_instructions

FAKE_CONFIG = """
default:
  instructions: "You are a helpful assistant."

recommendation:
  instructions: "You are a recommendation agent."
"""

CONFIG_NO_DEFAULT = """
cotacao:
  instructions: "You are a pricing agent."
"""


def test_load_known_agent_returns_its_instructions():
    with patch("builtins.open", mock_open(read_data=FAKE_CONFIG)):
        result = load_instructions("recommendation")
    assert "recommendation agent" in result


def test_load_unknown_agent_falls_back_to_default():
    with patch("builtins.open", mock_open(read_data=FAKE_CONFIG)):
        result = load_instructions("unknown_agent")
    assert "helpful assistant" in result


def test_load_default_agent_explicitly():
    with patch("builtins.open", mock_open(read_data=FAKE_CONFIG)):
        result = load_instructions("default")
    assert "helpful assistant" in result


def test_load_returns_empty_when_agent_and_default_missing():
    with patch("builtins.open", mock_open(read_data=CONFIG_NO_DEFAULT)):
        result = load_instructions("unknown")
    assert result == ""


def test_load_returns_empty_when_config_is_empty():
    with patch("builtins.open", mock_open(read_data="")):
        result = load_instructions("default")
    assert result == ""


def test_load_returns_empty_when_entry_has_no_instructions_key():
    config = "default:\n  description: 'something'\n"
    with patch("builtins.open", mock_open(read_data=config)):
        result = load_instructions("default")
    assert result == ""
