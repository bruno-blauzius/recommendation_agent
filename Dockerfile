# =====================================================================
# Stage 1 — Builder: compile Python wheels that require a C compiler.
# gcc never reaches the runtime image.
# =====================================================================
FROM python:3.12-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Install into an isolated venv so it can be cleanly copied to the next stage
RUN python -m venv /venv \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt

# =====================================================================
# Stage 2 — Runtime: lean image without build tools
# =====================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Make the venv the active Python environment
    PATH="/venv/bin:$PATH"

# Install Node.js 20 LTS via NodeSource, then remove curl (not needed at runtime).
# All apt operations in a single layer to minimise image size.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

# Pre-install MCP filesystem server at a pinned version.
# Avoids internet access and download latency on the first agent call.
RUN npm install -g @modelcontextprotocol/server-filesystem@2026.1.14 \
    && npm cache clean --force

# Copy compiled Python packages from the builder stage
COPY --from=builder /venv /venv

# Run as a non-root user (OWASP least-privilege principle)
RUN useradd --no-create-home --shell /bin/false appuser

WORKDIR /app
COPY . .
RUN chown -R appuser:appuser /app

USER appuser

CMD ["python", "main.py"]
