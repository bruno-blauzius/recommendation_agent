import logging
from pathlib import Path

from infraestructure.databases.base import DatabaseAdapter

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
MIGRATIONS_TABLE = "schema_migrations"


async def create_migrations_table(db: DatabaseAdapter) -> None:
    """Create the schema_migrations table if it doesn't exist."""
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) UNIQUE NOT NULL,
        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    try:
        await db.execute(create_table_sql)
        logger.debug("Migrations tracking table ensured")
    except Exception as e:
        logger.error("Failed to create migrations table: %s", str(e))
        raise


async def is_migration_executed(db: DatabaseAdapter, name: str) -> bool:
    """Check if a migration has already been executed."""
    query = f"SELECT 1 FROM {MIGRATIONS_TABLE} WHERE name = $1"
    result = await db.fetchrow(query, name)
    return result is not None


async def record_migration(db: DatabaseAdapter, name: str) -> None:
    """Record a migration execution."""
    insert_query = f"""
    INSERT INTO {MIGRATIONS_TABLE} (name, executed_at)
    VALUES ($1, CURRENT_TIMESTAMP)
    ON CONFLICT (name) DO NOTHING;
    """
    await db.execute(insert_query, name)


def get_migration_files() -> list[Path]:
    """Return all SQL migration files sorted by name."""
    if not MIGRATIONS_DIR.exists():
        return []

    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    return sql_files


async def execute_migrations(db: DatabaseAdapter) -> None:
    """Execute all pending migrations."""
    # Ensure migrations table exists
    await create_migrations_table(db)

    migration_files = get_migration_files()

    if not migration_files:
        logger.warning("No migration files found in %s", MIGRATIONS_DIR)
        return

    logger.info("Found %d migration file(s)", len(migration_files))

    executed_count = 0
    skipped_count = 0

    for migration_file in migration_files:
        # Check if migration already executed
        if await is_migration_executed(db, migration_file.name):
            logger.info(
                "⊘ Migration %s already executed (skipped)", migration_file.name
            )
            skipped_count += 1
            continue

        logger.info("Executing migration: %s", migration_file.name)
        sql_content = migration_file.read_text(encoding="utf-8")

        try:
            await db.execute(sql_content)
            await record_migration(db, migration_file.name)
            logger.info("✓ Migration %s completed successfully", migration_file.name)
            executed_count += 1
        except Exception as e:
            logger.error(
                "✗ Migration %s failed: %s",
                migration_file.name,
                str(e),
            )
            raise

    logger.info(
        "Migrations summary: %d executed, %d skipped",
        executed_count,
        skipped_count,
    )


async def run_migrations(dsn: str) -> None:
    """Run all migrations against the database."""
    from infraestructure.databases.postgres import PostgresDatabase

    async with PostgresDatabase(dsn=dsn) as db:
        await execute_migrations(db)
        logger.info("All migrations processed successfully")
