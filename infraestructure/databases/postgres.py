import asyncpg

from infraestructure.databases.base import DatabaseAdapter


class PostgresDatabase(DatabaseAdapter):

    def __init__(
        self,
        dsn: str,
        min_size: int = 2,
        max_size: int = 10,
    ) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
        )

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "PostgresDatabase":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError(
                "Database pool is not initialised. Call connect() first."
            )
        return self._pool

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def execute(self, query: str, *args) -> None:
        await self._get_pool().execute(query, *args)

    async def execute_many(self, query: str, args_list: list) -> None:
        await self._get_pool().executemany(query, args_list)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def fetch(self, query: str, *args) -> list[dict]:
        rows = await self._get_pool().fetch(query, *args)
        return [dict(row) for row in rows]

    async def fetchrow(self, query: str, *args) -> dict | None:
        row = await self._get_pool().fetchrow(query, *args)
        return dict(row) if row else None

    async def fetchval(self, query: str, *args):
        return await self._get_pool().fetchval(query, *args)

    # ------------------------------------------------------------------
    # Transaction support
    # ------------------------------------------------------------------

    async def execute_in_transaction(self, query: str, *args) -> None:
        async with self._get_pool().acquire() as conn:
            async with conn.transaction():
                await conn.execute(query, *args)
