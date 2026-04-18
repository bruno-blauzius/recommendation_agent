from abc import ABCMeta, abstractmethod

from agents import Agent

from agent_core.instructions import load_instructions


class AgentAdapter(metaclass=ABCMeta):

    def __init__(self, name: str, model_name: str):
        self.name = name
        self.model_name = model_name
        instructions = load_instructions(name)
        if not instructions:
            raise ValueError(f"No instructions found for agent '{name}' in config.yml")
        self.instructions: str = instructions

    @abstractmethod
    def create_agent(
        self,
        mcp_servers: list | None = None,
        input_guardrails: list | None = None,
        output_guardrails: list | None = None,
    ) -> Agent:
        """Create and return an Agent instance
        configured with optional MCPs and guardrails."""
        pass
