import uuid
from datetime import timezone

import pytest
from pydantic import ValidationError

from schemas.message import (
    AgentMessage,
    AgentMessageResult,
    AgentType,
    MessagePriority,
)


# ---------------------------------------------------------------------------
# AgentType enum
# ---------------------------------------------------------------------------


def test_agent_type_default_value():
    assert AgentType.DEFAULT == "default"


def test_agent_type_recommendation_products_value():
    assert AgentType.RECOMMENDATION_PRODUCTS == "recommendation_products"


def test_agent_type_invalid_raises():
    with pytest.raises(ValidationError):
        AgentMessage(prompt="hello", agent_type="unknown_type")


# ---------------------------------------------------------------------------
# MessagePriority enum
# ---------------------------------------------------------------------------


def test_priority_values():
    assert MessagePriority.LOW == "low"
    assert MessagePriority.NORMAL == "normal"
    assert MessagePriority.HIGH == "high"


def test_priority_invalid_raises():
    with pytest.raises(ValidationError):
        AgentMessage(prompt="hello", priority="urgent")


# ---------------------------------------------------------------------------
# AgentMessage — defaults
# ---------------------------------------------------------------------------


def test_message_default_agent_type():
    msg = AgentMessage(prompt="hello")
    assert msg.agent_type == AgentType.DEFAULT


def test_message_default_priority():
    msg = AgentMessage(prompt="hello")
    assert msg.priority == MessagePriority.NORMAL


def test_message_default_metadata_is_empty_dict():
    msg = AgentMessage(prompt="hello")
    assert msg.metadata == {}


def test_message_id_is_valid_uuid():
    msg = AgentMessage(prompt="hello")
    uuid.UUID(msg.message_id)  # raises ValueError if invalid


def test_correlation_id_is_valid_uuid():
    msg = AgentMessage(prompt="hello")
    uuid.UUID(msg.correlation_id)  # raises ValueError if invalid


def test_message_id_is_unique_per_instance():
    m1 = AgentMessage(prompt="hello")
    m2 = AgentMessage(prompt="hello")
    assert m1.message_id != m2.message_id


def test_created_at_is_utc():
    msg = AgentMessage(prompt="hello")
    assert msg.created_at.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# AgentMessage — prompt validation
# ---------------------------------------------------------------------------


def test_prompt_required():
    with pytest.raises(ValidationError):
        AgentMessage()


def test_prompt_empty_string_raises():
    with pytest.raises(ValidationError):
        AgentMessage(prompt="")


def test_prompt_whitespace_only_raises():
    with pytest.raises(ValidationError):
        AgentMessage(prompt="   ")


def test_prompt_max_length_boundary():
    msg = AgentMessage(prompt="x" * 10_000)
    assert len(msg.prompt) == 10_000


def test_prompt_exceeds_max_length_raises():
    with pytest.raises(ValidationError):
        AgentMessage(prompt="x" * 10_001)


def test_prompt_min_length_one_char():
    msg = AgentMessage(prompt="a")
    assert msg.prompt == "a"


# ---------------------------------------------------------------------------
# AgentMessage — ID validation
# ---------------------------------------------------------------------------


def test_custom_message_id_accepted():
    custom_id = str(uuid.uuid4())
    msg = AgentMessage(prompt="hello", message_id=custom_id)
    assert msg.message_id == custom_id


def test_blank_message_id_raises():
    with pytest.raises(ValidationError):
        AgentMessage(prompt="hello", message_id="   ")


def test_blank_correlation_id_raises():
    with pytest.raises(ValidationError):
        AgentMessage(prompt="hello", correlation_id="")


# ---------------------------------------------------------------------------
# AgentMessage — metadata
# ---------------------------------------------------------------------------


def test_metadata_accepts_arbitrary_values():
    msg = AgentMessage(
        prompt="hello",
        metadata={"tenant_id": "t-001", "retry_count": 2, "tags": ["a", "b"]},
    )
    assert msg.metadata["tenant_id"] == "t-001"
    assert msg.metadata["retry_count"] == 2


# ---------------------------------------------------------------------------
# AgentMessage — serialization
# ---------------------------------------------------------------------------


def test_model_dump_contains_all_fields():
    msg = AgentMessage(prompt="test prompt")
    data = msg.model_dump()
    assert "message_id" in data
    assert "correlation_id" in data
    assert "agent_type" in data
    assert "prompt" in data
    assert "priority" in data
    assert "metadata" in data
    assert "created_at" in data


def test_model_dump_json_is_valid_string():
    msg = AgentMessage(prompt="test prompt")
    json_str = msg.model_dump_json()
    assert isinstance(json_str, str)
    assert "test prompt" in json_str


def test_round_trip_from_dict():
    original = AgentMessage(
        prompt="recommend products",
        agent_type=AgentType.RECOMMENDATION_PRODUCTS,
        priority=MessagePriority.HIGH,
        metadata={"source": "sqs"},
    )
    data = original.model_dump()
    restored = AgentMessage(**data)
    assert restored.message_id == original.message_id
    assert restored.agent_type == original.agent_type
    assert restored.prompt == original.prompt


# ---------------------------------------------------------------------------
# AgentMessageResult — success
# ---------------------------------------------------------------------------


def test_result_success():
    result = AgentMessageResult(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        agent_type=AgentType.DEFAULT,
        success=True,
        response="Here are the best products.",
    )
    assert result.success is True
    assert result.error is None
    assert result.response == "Here are the best products."


def test_result_failure():
    result = AgentMessageResult(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        agent_type=AgentType.DEFAULT,
        success=False,
        error="RateLimitError: too many requests",
    )
    assert result.success is False
    assert result.response is None
    assert "RateLimitError" in result.error


def test_result_processed_at_is_utc():
    result = AgentMessageResult(
        message_id=str(uuid.uuid4()),
        correlation_id=str(uuid.uuid4()),
        agent_type=AgentType.DEFAULT,
        success=True,
    )
    assert result.processed_at.tzinfo == timezone.utc


def test_result_echoes_message_and_correlation_ids():
    msg_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())
    result = AgentMessageResult(
        message_id=msg_id,
        correlation_id=corr_id,
        agent_type=AgentType.RECOMMENDATION_PRODUCTS,
        success=True,
        response="ok",
    )
    assert result.message_id == msg_id
    assert result.correlation_id == corr_id
