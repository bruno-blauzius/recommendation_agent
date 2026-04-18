from agents import Agent

from agent_core.agent_adapter import AgentAdapter
from agents.extensions.models.litellm_model import LitellmModel


class AgentClaude(AgentAdapter):

    def __init__(self, name: str, model_name: str):
        super().__init__(name, model_name)
        self._litellm_model = LitellmModel(model=model_name)

    def create_agent(
        self,
        mcp_servers: list | None = None,
        input_guardrails: list | None = None,
        output_guardrails: list | None = None,
    ) -> Agent:
        try:
            return Agent(
                name=self.name,
                model=self._litellm_model,
                instructions=self.instructions,
                mcp_servers=mcp_servers or [],
                input_guardrails=input_guardrails or [],
                output_guardrails=output_guardrails or [],
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create Claude agent: {str(e)}")
