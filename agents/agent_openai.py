from agents import Agent

from agents.agent_adapter import AgentAdapter


class AgentOpenAI(AgentAdapter):

    def __init__(self, name: str, model_name: str):
        super().__init__(name, model_name)

    def create_agent(
        self,
        mcp_servers: list | None = None,
        input_guardrails: list | None = None,
        output_guardrails: list | None = None,
    ) -> Agent:
        try:
            return Agent(
                name=self.name,
                model=self.model_name,
                instructions=self.instructions,
                mcp_servers=mcp_servers or [],
                input_guardrails=input_guardrails or [],
                output_guardrails=output_guardrails or [],
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create OpenAI agent: {str(e)}")
