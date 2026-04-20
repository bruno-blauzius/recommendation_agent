import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AgentType(str, Enum):
    DEFAULT = "default"
    RECOMMENDATION_PRODUCTS = "recommendation_products"


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class AgentMessage(BaseModel):
    """Envelope for messages received from SQS / RabbitMQ.

    Fields:
        message_id:     Unique identifier for deduplication (idempotency key).
        correlation_id: Caller-supplied ID to correlate request ↔ response.
        agent_type:     Which agent pipeline to invoke.
        prompt:         The user/system prompt to be processed.
        priority:       Processing priority hint for the consumer.
        metadata:       Arbitrary caller-supplied key/value pairs.
        created_at:     ISO-8601 UTC timestamp set by the producer.
    """

    message_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique message ID used for deduplication.",
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Caller-supplied ID to correlate request and response.",
    )
    agent_type: AgentType = Field(
        default=AgentType.DEFAULT,
        description="Agent pipeline to invoke.",
    )
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="Prompt to be processed by the agent.",
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Processing priority hint.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary caller-supplied key/value pairs.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp set by the producer.",
    )

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt must not be blank or whitespace-only")
        return v

    @field_validator("message_id", "correlation_id")
    @classmethod
    def id_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ID fields must not be blank")
        return v

    model_config = {"str_strip_whitespace": False}


class AgentMessageResult(BaseModel):
    """Result envelope written back to the response queue or stored."""

    message_id: str = Field(description="Echoes the originating message_id.")
    correlation_id: str = Field(description="Echoes the originating correlation_id.")
    agent_type: AgentType
    success: bool
    response: str | None = Field(
        default=None,
        description="Agent output on success.",
    )
    error: str | None = Field(
        default=None,
        description="Error detail on failure.",
    )
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when processing completed.",
    )
