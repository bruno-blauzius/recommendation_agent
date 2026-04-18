from agents import Agent

from agents.agent_adapter import AgentAdapter


class AgentOpenAI(AgentAdapter):

    def __init__(self, name: str, model_name: str):
        super().__init__(name, model_name)

    def create_agent(self) -> Agent:
        # Placeholder implementation - replace with actual logic
        agent_id = f"agent_{self.name.lower()}"
        try:
            return Agent(
                id=agent_id,
                name=self.name,
                model=self.model_name,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create OpenAI agent: {str(e)}")
