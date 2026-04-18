from abc import ABCMeta, abstractmethod

from agents import Agent


class AgentAdapter(metaclass=ABCMeta):

    def __init__(self, name: str, model_name: str):
        self.name = name
        self.model_name = model_name

    @abstractmethod
    def create_agent(
        self,
    ) -> Agent:
        """Create and return an Agent instance."""
        pass
