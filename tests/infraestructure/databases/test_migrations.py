from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infraestructure.migration_manager import (
    create_migrations_table,
    execute_migrations,
    get_migration_files,
    is_migration_executed,
    record_migration,
    run_migrations,
)


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.close = AsyncMock()
    pool.execute = AsyncMock()
    pool.fetchrow = AsyncMock()
    pool.executemany = AsyncMock()
    pool.fetchval = AsyncMock(return_value=0)
    pool.fetch = AsyncMock(return_value=[])

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
    from infraestructure.databases.postgres import PostgresDatabase

    with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)):
        async with PostgresDatabase(dsn="postgresql://test") as database:
            yield database


# ---------------------------------------------------------------------------
# create_migrations_table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_migrations_table(db, mock_pool):
    await create_migrations_table(db)
    mock_pool.execute.assert_awaited_once()
    call_args = mock_pool.execute.call_args[0][0]
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in call_args


@pytest.mark.asyncio
async def test_create_migrations_table_raises_on_failure(db, mock_pool):
    mock_pool.execute.side_effect = Exception("db error")
    with pytest.raises(Exception, match="db error"):
        await create_migrations_table(db)


# ---------------------------------------------------------------------------
# is_migration_executed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_migration_executed_returns_true_when_exists(db, mock_pool):
    mock_pool.fetchrow.return_value = {"id": 1}
    result = await is_migration_executed(db, "001_test.sql")
    assert result is True
    mock_pool.fetchrow.assert_awaited_once()


@pytest.mark.asyncio
async def test_is_migration_executed_returns_false_when_not_exists(db, mock_pool):
    mock_pool.fetchrow.return_value = None
    result = await is_migration_executed(db, "999_nonexistent.sql")
    assert result is False


# ---------------------------------------------------------------------------
# record_migration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_migration_inserts_record(db, mock_pool):
    await record_migration(db, "001_test.sql")
    mock_pool.execute.assert_awaited_once()
    call_args = mock_pool.execute.call_args[0]
    assert "INSERT INTO schema_migrations" in call_args[0]
    assert call_args[1] == "001_test.sql"


# ---------------------------------------------------------------------------
# get_migration_files
# ---------------------------------------------------------------------------


def test_get_migration_files_returns_sorted_sql_files(tmp_path):
    (tmp_path / "002_b.sql").write_text("SELECT 2")
    (tmp_path / "001_a.sql").write_text("SELECT 1")
    (tmp_path / "not_a_migration.txt").write_text("ignore")

    with patch("infraestructure.migration_manager.MIGRATIONS_DIR", tmp_path):
        files = get_migration_files()

    assert len(files) == 2
    assert files[0].name == "001_a.sql"
    assert files[1].name == "002_b.sql"


def test_get_migration_files_returns_empty_when_dir_missing():
    with patch(
        "infraestructure.migration_manager.MIGRATIONS_DIR",
        Path("/nonexistent/path"),
    ):
        files = get_migration_files()
    assert files == []


# ---------------------------------------------------------------------------
# execute_migrations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_migrations_runs_pending_files(db, mock_pool, tmp_path):
    (tmp_path / "001_create.sql").write_text("CREATE TABLE foo (id SERIAL);")

    mock_pool.fetchrow.return_value = None  # migration not yet executed

    with patch("infraestructure.migration_manager.MIGRATIONS_DIR", tmp_path):
        await execute_migrations(db)

    # execute: 1x create_migrations_table + 1x migration SQL + 1x record_migration
    assert mock_pool.execute.await_count == 3


@pytest.mark.asyncio
async def test_execute_migrations_skips_already_executed(db, mock_pool, tmp_path):
    (tmp_path / "001_create.sql").write_text("CREATE TABLE foo (id SERIAL);")

    mock_pool.fetchrow.return_value = {"id": 1}  # already executed

    with patch("infraestructure.migration_manager.MIGRATIONS_DIR", tmp_path):
        await execute_migrations(db)

    # execute called only 1x for create_migrations_table — migration skipped
    mock_pool.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_migrations_no_files(db, mock_pool, tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with patch("infraestructure.migration_manager.MIGRATIONS_DIR", empty_dir):
        await execute_migrations(db)

    # only create_migrations_table called
    mock_pool.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_migrations_raises_on_sql_failure(db, mock_pool, tmp_path):
    (tmp_path / "001_bad.sql").write_text("INVALID SQL;")

    mock_pool.fetchrow.return_value = None  # not executed yet

    # First call: create_migrations_table (ok). Second call: migration SQL (fails).
    mock_pool.execute.side_effect = [None, Exception("syntax error")]

    with patch("infraestructure.migration_manager.MIGRATIONS_DIR", tmp_path):
        with pytest.raises(Exception, match="syntax error"):
            await execute_migrations(db)


# ---------------------------------------------------------------------------
# run_migrations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_migrations_calls_execute_migrations(mock_pool, tmp_path):
    with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)):
        with patch("infraestructure.migration_manager.MIGRATIONS_DIR", tmp_path):
            await run_migrations("postgresql://user:pass@localhost/db")

    # Ensured migrations table was created
    mock_pool.execute.assert_awaited_once()
