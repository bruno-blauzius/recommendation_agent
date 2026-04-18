from agents import Runner
from litellm.exceptions import RateLimitError, InternalServerError

# from agents.mcp import MCPServerStdio
from agents.agent_adapter import AgentAdapter


class AgentService:

    def __init__(self, model_adapter: AgentAdapter):
        self.adapter = model_adapter

    def invoke(self, prompt: str, mcps: list = [], guardrails: list = []) -> dict:
        agent = self.adapter.create_agent()

        runner = Runner(agent=agent, extensions=mcps, guardrails=guardrails)

        try:
            response = runner.run(prompt)
            return {"response": response}
        except (RateLimitError, InternalServerError) as e:
            return {"error": str(e)}
