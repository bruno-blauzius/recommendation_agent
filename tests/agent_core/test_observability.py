from unittest.mock import patch

import litellm
import pytest

import agent_core.observability as obs_module
from agent_core.observability import configure_litellm


@pytest.fixture(autouse=True)
def _reset_configured():
    """Reset the module-level _configured flag before each test."""
    obs_module._configured = False
    yield
    obs_module._configured = False


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_configure_litellm_runs_once(monkeypatch):
    monkeypatch.setenv("LITELLM_SUCCESS_CALLBACKS", "langfuse")
    configure_litellm()
    configure_litellm()  # second call must be a no-op

    assert obs_module._configured is True


def test_second_call_does_not_overwrite_callbacks(monkeypatch):
    monkeypatch.setenv("LITELLM_SUCCESS_CALLBACKS", "langfuse")
    configure_litellm()

    with patch.object(litellm, "success_callback", []) as _:
        monkeypatch.setenv("LITELLM_SUCCESS_CALLBACKS", "prometheus")
        configure_litellm()  # must not run again

    # litellm.success_callback was NOT overwritten because _configured == True
    assert obs_module._configured is True


# ---------------------------------------------------------------------------
# Success callbacks
# ---------------------------------------------------------------------------


def test_success_callbacks_set_from_env(monkeypatch):
    monkeypatch.setenv("LITELLM_SUCCESS_CALLBACKS", "langfuse,prometheus")
    configure_litellm()
    assert litellm.success_callback == ["langfuse", "prometheus"]


def test_success_callbacks_strips_whitespace(monkeypatch):
    monkeypatch.setenv("LITELLM_SUCCESS_CALLBACKS", " langfuse , prometheus ")
    configure_litellm()
    assert litellm.success_callback == ["langfuse", "prometheus"]


def test_success_callbacks_not_set_when_env_empty(monkeypatch):
    monkeypatch.setenv("LITELLM_SUCCESS_CALLBACKS", "")
    original = litellm.success_callback
    configure_litellm()
    assert litellm.success_callback == original


def test_success_callbacks_not_set_when_env_absent(monkeypatch):
    monkeypatch.delenv("LITELLM_SUCCESS_CALLBACKS", raising=False)
    original = litellm.success_callback
    configure_litellm()
    assert litellm.success_callback == original


# ---------------------------------------------------------------------------
# Failure callbacks
# ---------------------------------------------------------------------------


def test_failure_callbacks_set_from_env(monkeypatch):
    monkeypatch.setenv("LITELLM_FAILURE_CALLBACKS", "langfuse")
    configure_litellm()
    assert litellm.failure_callback == ["langfuse"]


def test_failure_callbacks_strips_whitespace(monkeypatch):
    monkeypatch.setenv("LITELLM_FAILURE_CALLBACKS", " langfuse , datadog ")
    configure_litellm()
    assert litellm.failure_callback == ["langfuse", "datadog"]


def test_failure_callbacks_not_set_when_env_empty(monkeypatch):
    monkeypatch.setenv("LITELLM_FAILURE_CALLBACKS", "")
    original = litellm.failure_callback
    configure_litellm()
    assert litellm.failure_callback == original


def test_failure_callbacks_not_set_when_env_absent(monkeypatch):
    monkeypatch.delenv("LITELLM_FAILURE_CALLBACKS", raising=False)
    original = litellm.failure_callback
    configure_litellm()
    assert litellm.failure_callback == original


# ---------------------------------------------------------------------------
# Verbose flag
# ---------------------------------------------------------------------------


def test_verbose_enabled_when_env_true(monkeypatch):
    monkeypatch.setenv("LITELLM_VERBOSE", "true")
    configure_litellm()
    assert litellm.set_verbose is True


def test_verbose_disabled_when_env_false(monkeypatch):
    monkeypatch.setenv("LITELLM_VERBOSE", "false")
    configure_litellm()
    assert litellm.set_verbose is False


def test_verbose_disabled_when_env_absent(monkeypatch):
    monkeypatch.delenv("LITELLM_VERBOSE", raising=False)
    configure_litellm()
    assert litellm.set_verbose is False


def test_verbose_case_insensitive(monkeypatch):
    monkeypatch.setenv("LITELLM_VERBOSE", "TRUE")
    configure_litellm()
    assert litellm.set_verbose is True


# ---------------------------------------------------------------------------
# _configured flag
# ---------------------------------------------------------------------------


def test_configured_flag_set_after_call():
    configure_litellm()
    assert obs_module._configured is True


def test_configured_flag_false_before_call():
    assert obs_module._configured is False
