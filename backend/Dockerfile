FROM python:3.10-slim

# Install uv from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files before source code so Docker can cache this layer.
# If only source code changes (not dependencies), this expensive install step
# is skipped on the next build.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy application source
COPY backend/ ./backend/
COPY dbt/ ./dbt/

# Download dbt packages (dbt_packages/ is excluded from the build context
# via .dockerignore since it's gitignored and may be stale locally)
RUN cd dbt && /app/.venv/bin/dbt deps --profiles-dir .

# Make backend/ importable as a package root (so 'from app.xxx import' works)
ENV PYTHONPATH=/app/backend

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
