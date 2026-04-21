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

_REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
_REDIS_PORT = os.getenv("REDIS_PORT", "6379")
_REDIS_DB = os.getenv("REDIS_DB", "0")

# RABBITMQ
_RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
_RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "agent.tasks")
_RABBITMQ_DLX = os.getenv("RABBITMQ_DLX", "agent.dlx")
_RABBITMQ_PREFETCH = int(os.getenv("RABBITMQ_PREFETCH", "10"))
_REDIS_URL = f"redis://{_REDIS_HOST}:{_REDIS_PORT}/{_REDIS_DB}"
_AGENT_MAX_CONCURRENCY = int(os.getenv("AGENT_MAX_CONCURRENCY", "10"))
# Maximum wall-clock time (seconds) allowed for a single agent invocation.
# Prevents a hung LLM call from blocking the worker indefinitely.
_AGENT_DISPATCH_TIMEOUT = float(os.getenv("AGENT_DISPATCH_TIMEOUT_SECONDS", "300"))

_GPT_MODEL_TEXT = os.getenv("GPT_MODEL_TEXT", "gpt-4o-mini")
