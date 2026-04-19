import contextlib

from agents import Runner
from agents.mcp import MCPServerStdio
from litellm.exceptions import RateLimitError, InternalServerError

from agent_core.agent_adapter import AgentAdapter
from agent_core.observability import configure_litellm


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
    ) -> dict:
        mcp_list = mcp_servers or []
        agent = self.adapter.create_agent(
            mcp_servers=mcp_list,
            input_guardrails=input_guardrails,
            output_guardrails=output_guardrails,
        )
        try:
            async with contextlib.AsyncExitStack() as stack:
                for mcp in mcp_list:
                    await stack.enter_async_context(mcp)
                result = await Runner.run(agent, input=prompt)
            return {"response": result.final_output}
        except (RateLimitError, InternalServerError) as e:
            return {"error": str(e)}
