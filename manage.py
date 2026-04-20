import asyncio
import logging
import sys
from tabulate import tabulate

from dotenv import load_dotenv

from infraestructure.migration_manager import run_migrations
from infraestructure.databases.postgres import PostgresDatabase
from settings import _DB_HOST, _DB_NAME, _DB_PASSWORD, _DB_PORT, _DB_USER

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Get database URL from environment variables."""
    user = _DB_USER
    password = _DB_PASSWORD
    host = _DB_HOST
    port = _DB_PORT
    database = _DB_NAME

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def get_safe_database_url() -> str:
    """Get database URL with masked password for logging."""
    user = _DB_USER
    host = _DB_HOST
    port = _DB_PORT
    database = _DB_NAME

    return f"postgresql://{user}:***@{host}:{port}/{database}"


def migrate(args=None):
    """Run database migrations."""
    try:
        dsn = get_database_url()
        logger.info("Connecting to database: %s", get_safe_database_url())
        asyncio.run(run_migrations(dsn))
        logger.info("✓ Migrations completed successfully")
    except Exception as e:
        logger.error("✗ Migration failed: %s", str(e))
        sys.exit(1)


async def list_executed_migrations_async(dsn: str) -> None:
    """List all executed migrations."""
    try:
        async with PostgresDatabase(dsn=dsn) as db:
            migrations = await db.fetch(
                """
                SELECT name, executed_at
                FROM schema_migrations
                ORDER BY executed_at ASC
                """
            )

            if not migrations:
                print("No migrations executed yet.")
                return

            table_data = [
                [m["name"], m["executed_at"].strftime("%Y-%m-%d %H:%M:%S")]
                for m in migrations
            ]
            headers = ["Migration", "Executed At"]

            print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))
            print(f"\nTotal: {len(migrations)} migration(s) executed\n")
    except Exception as e:
        logger.error("Failed to list migrations: %s", str(e))
        sys.exit(1)


def migrations_list(args=None):
    """List all executed migrations."""
    try:
        dsn = get_database_url()
        asyncio.run(list_executed_migrations_async(dsn))
    except Exception as e:
        logger.error("✗ Failed to list migrations: %s", str(e))
        sys.exit(1)


def help_command(args=None):
    """Show available commands."""
    print(
        """
Available commands:

  python manage.py migrate
    Execute all pending migrations from infraestructure/migrations/*.sql

  python manage.py migrations-list
    List all executed migrations

  python manage.py help
    Show this help message
"""
    )


COMMANDS = {
    "migrate": migrate,
    "migrations-list": migrations_list,
    "help": help_command,
}


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python manage.py <command>")
        print("Run 'python manage.py help' for available commands")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else None

    if command not in COMMANDS:
        print(f"Unknown command: {command}")
        print("Run 'python manage.py help' for available commands")
        sys.exit(1)

    COMMANDS[command](args)


if __name__ == "__main__":
    main()
