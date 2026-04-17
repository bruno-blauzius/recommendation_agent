from abc import ABC, abstractmethod
from typing import Any


class DatabaseAdapter(ABC):

    @abstractmethod
    async def connect(self) -> None:
        """Establish the connection / pool."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection / pool."""

    @abstractmethod
    async def execute(self, query: str, *args: Any) -> None:
        """Execute a write statement (INSERT, UPDATE, DELETE)."""

    @abstractmethod
    async def fetch(self, query: str, *args: Any) -> list[dict]:
        """Execute a read statement and return all rows."""

    @abstractmethod
    async def fetchrow(self, query: str, *args: Any) -> dict | None:
        """Execute a read statement and return a single row."""
