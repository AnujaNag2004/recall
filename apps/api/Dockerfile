# Build context: apps/api
FROM python:3.12-slim

ENV UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependencies first, so editing app code does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

RUN useradd --create-home recall && chown -R recall /app
USER recall

# Render injects PORT; 8000 is the local default.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
