# Builder stage - install dependencies with uv
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation and use system Python
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency files first for better cache
COPY pyproject.toml ./

# Install dependencies only (run from source, not installed package)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && \
    uv pip install beautifulsoup4 click numpy orjson PyYAML scikit-learn sqlalchemy alembic fastapi "uvicorn[standard]" jinja2 tomli

# Production stage
FROM python:3.11-slim-bookworm

WORKDIR /app

# Create non-root user
RUN groupadd --gid 999 cerebro && \
    useradd --uid 999 --gid cerebro --shell /bin/bash --create-home cerebro

# Copy virtual environment from builder
COPY --from=builder --chown=cerebro:cerebro /app/.venv /app/.venv

# Add venv to PATH and set PYTHONPATH for src layout
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Copy application code and config
COPY --chown=cerebro:cerebro src/ ./src/
COPY --chown=cerebro:cerebro pyproject.toml taxonomy.yaml ./

# Expose ports for serve and dashboard
EXPOSE 8765 8080

# Switch to non-root user
USER cerebro

# Default command: start the ingestion server (run from source)
CMD ["python", "-m", "cerebro.cli", "serve", "--host", "0.0.0.0", "--port", "8765"]
