import os


_ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ---------------------------------------------------------------------------
# Retry / backoff defaults — all tunable via environment variables
# ---------------------------------------------------------------------------
_MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "4"))
_BACKOFF_BASE = float(os.getenv("AGENT_BACKOFF_BASE_SECONDS", "1.0"))
_BACKOFF_MAX = float(os.getenv("AGENT_BACKOFF_MAX_SECONDS", "60.0"))

# DATABASE POSTGRES
_DB_USER = os.getenv("DB_USER", "postgres")
_DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
_DB_HOST = os.getenv("DB_HOST", "localhost")
_DB_PORT = os.getenv("DB_PORT", "5432")
_DB_NAME = os.getenv("DB_NAME", "recommendation_agent")


# RABBITMQ
_RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
_RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "agent.tasks")
_RABBITMQ_DLX = os.getenv("RABBITMQ_DLX", "agent.dlx")
_RABBITMQ_PREFETCH = int(os.getenv("RABBITMQ_PREFETCH", "10"))
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_AGENT_MAX_CONCURRENCY = int(os.getenv("AGENT_MAX_CONCURRENCY", "10"))
