import asyncio
import contextlib
import logging
import random

from settings import _MAX_RETRIES, _BACKOFF_BASE, _BACKOFF_MAX

from agents import Runner
from agents.mcp import MCPServerStdio
from litellm.exceptions import RateLimitError, InternalServerError

from agent_core.agent_adapter import AgentAdapter
from agent_core.observability import configure_litellm

logger = logging.getLogger("agent_core.agent_service")


# Exceptions that warrant a retry (transient LLM-provider errors)
_RETRYABLE = (RateLimitError, InternalServerError)


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with full jitter.

    delay = min(base * 2^attempt, max) + uniform(0, 1)

    Full jitter avoids thundering-herd when many workers hit rate-limits
    simultaneously and retry at the same instant.
    """
    exp = _BACKOFF_BASE * (2**attempt)
    return min(exp, _BACKOFF_MAX) + random.uniform(0, 1)


class AgentService:

    def __init__(self, model_adapter: AgentAdapter):
        self.adapter = model_adapter
        configure_litellm()

    async def invoke(
        self,
        prompt: str,
        mcp_servers: list[MCPServerStdio] | None = None,
        input_guardrails: list | None = None,
        output_guardrails: list | None = None,
        tools: list | None = None,
    ) -> dict:
        mcp_list = mcp_servers or []
        agent = self.adapter.create_agent(
            mcp_servers=mcp_list,
            input_guardrails=input_guardrails,
            output_guardrails=output_guardrails,
            tools=tools,
        )

        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                async with contextlib.AsyncExitStack() as stack:
                    for mcp in mcp_list:
                        await stack.enter_async_context(mcp)
                    result = await Runner.run(agent, input=prompt)

                logger.info("Agent invocation succeeded (attempt=%d)", attempt + 1)
                return {"response": result.final_output}

            except _RETRYABLE as e:
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    delay = _backoff_delay(attempt)
                    logger.warning(
                        "Transient error on attempt %d/%d — retrying in %.2fs: %s",
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "All %d attempts exhausted. Last error: %s",
                        _MAX_RETRIES,
                        e,
                    )

        return {"error": str(last_error)}
