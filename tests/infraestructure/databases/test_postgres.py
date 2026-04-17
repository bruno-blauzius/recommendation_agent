from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infraestructure.databases.postgres import PostgresDatabase


DSN = "postgresql://user:password@localhost:5432/testdb"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.close = AsyncMock()
    pool.execute = AsyncMock()
    pool.executemany = AsyncMock()
    pool.fetchval = AsyncMock(return_value=1)

    fetch_row = MagicMock()
    fetch_row.items = MagicMock(
        return_value=[("id", 1), ("nome", "João"), ("email", "joao@email.com")]
    )
    fetch_row.__iter__ = MagicMock(
        return_value=iter([("id", 1), ("nome", "João"), ("email", "joao@email.com")])
    )
    pool.fetchrow = AsyncMock(return_value=fetch_row)

    fetch_record = MagicMock()
    fetch_record.__iter__ = MagicMock(
        return_value=iter([("id", 1), ("nome", "João"), ("email", "joao@email.com")])
    )
    pool.fetch = AsyncMock(return_value=[fetch_record])

    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.transaction = MagicMock(
        return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock())
    )
    pool.acquire = MagicMock(
        return_value=MagicMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(),
        )
    )
    return pool


@pytest.fixture
async def db(mock_pool):
    with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)):
        async with PostgresDatabase(dsn=DSN) as database:
            yield database


# ---------------------------------------------------------------------------
# connect / disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_creates_pool(mock_pool):
    with patch(
        "asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)
    ) as mock_create:
        db = PostgresDatabase(dsn=DSN, min_size=2, max_size=5)
        await db.connect()

        mock_create.assert_awaited_once_with(dsn=DSN, min_size=2, max_size=5)
        assert db._pool is mock_pool

        await db.disconnect()


@pytest.mark.asyncio
async def test_disconnect_closes_pool(mock_pool):
    with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)):
        db = PostgresDatabase(dsn=DSN)
        await db.connect()
        await db.disconnect()

        mock_pool.close.assert_awaited_once()
        assert db._pool is None


@pytest.mark.asyncio
async def test_disconnect_without_connect_is_safe():
    db = PostgresDatabase(dsn=DSN)
    await db.disconnect()  # não deve lançar exceção


# ---------------------------------------------------------------------------
# Pool não inicializado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_raises_when_not_connected():
    db = PostgresDatabase(dsn=DSN)
    with pytest.raises(RuntimeError, match="not initialised"):
        await db.execute("SELECT 1")


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_insert(db, mock_pool):
    await db.execute(
        "INSERT INTO clientes (nome, email) VALUES ($1, $2)",
        "João",
        "joao@email.com",
    )
    mock_pool.execute.assert_awaited_once_with(
        "INSERT INTO clientes (nome, email) VALUES ($1, $2)",
        "João",
        "joao@email.com",
    )


@pytest.mark.asyncio
async def test_execute_update(db, mock_pool):
    await db.execute(
        "UPDATE clientes SET email = $1 WHERE id = $2", "novo@email.com", 1
    )
    mock_pool.execute.assert_awaited_once_with(
        "UPDATE clientes SET email = $1 WHERE id = $2", "novo@email.com", 1
    )


@pytest.mark.asyncio
async def test_execute_delete(db, mock_pool):
    await db.execute("DELETE FROM clientes WHERE id = $1", 1)
    mock_pool.execute.assert_awaited_once_with("DELETE FROM clientes WHERE id = $1", 1)


# ---------------------------------------------------------------------------
# execute_many
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_many(db, mock_pool):
    records = [("Ana", "ana@email.com"), ("Carlos", "carlos@email.com")]
    await db.execute_many("INSERT INTO clientes (nome, email) VALUES ($1, $2)", records)
    mock_pool.executemany.assert_awaited_once_with(
        "INSERT INTO clientes (nome, email) VALUES ($1, $2)", records
    )


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_list_of_dicts(db, mock_pool):
    result = await db.fetch("SELECT * FROM clientes")
    assert isinstance(result, list)
    mock_pool.fetch.assert_awaited_once_with("SELECT * FROM clientes")


# ---------------------------------------------------------------------------
# fetchrow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetchrow_returns_dict(db, mock_pool):
    result = await db.fetchrow("SELECT * FROM clientes WHERE id = $1", 1)
    assert result is not None
    mock_pool.fetchrow.assert_awaited_once_with(
        "SELECT * FROM clientes WHERE id = $1", 1
    )


@pytest.mark.asyncio
async def test_fetchrow_returns_none_when_not_found(db, mock_pool):
    mock_pool.fetchrow.return_value = None
    result = await db.fetchrow("SELECT * FROM clientes WHERE id = $1", 999)
    assert result is None


# ---------------------------------------------------------------------------
# fetchval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetchval_returns_scalar(db, mock_pool):
    mock_pool.fetchval.return_value = 42
    result = await db.fetchval("SELECT COUNT(*) FROM clientes")
    assert result == 42
    mock_pool.fetchval.assert_awaited_once_with("SELECT COUNT(*) FROM clientes")


# ---------------------------------------------------------------------------
# execute_in_transaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_in_transaction(db, mock_pool):
    await db.execute_in_transaction(
        "UPDATE contas SET saldo = saldo - $1 WHERE id = $2", 100.0, 1
    )
    conn = await mock_pool.acquire().__aenter__()
    conn.execute.assert_awaited_once_with(
        "UPDATE contas SET saldo = saldo - $1 WHERE id = $2", 100.0, 1
    )
