FROM python:3.10-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Install Playwright's Chromium browser and its system dependencies.
# This adds ~400 MB but is only in the cron image, not backend or bot.
RUN /app/.venv/bin/playwright install chromium --with-deps

COPY backend/ ./backend/
COPY dbt/ ./dbt/

RUN cd dbt && /app/.venv/bin/dbt deps --profiles-dir .

ENV PYTHONPATH=/app/backend

CMD ["/app/.venv/bin/python", "backend/cron.py"]
