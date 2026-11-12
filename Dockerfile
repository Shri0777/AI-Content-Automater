# One image runs all three parts of the app: the web server, the background
# worker and the scheduler. docker-compose.yml picks which one to start.
FROM python:3.14-slim

# uv installs the exact package versions written in uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install packages before copying the code, so Docker can reuse this slow
# step when only the code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

# Run as a normal user instead of root. (V3's containers ran as root and
# left root-owned files in the project folder.) The media folder holds
# generated posters, so that user must be able to write to it.
RUN useradd --create-home appuser \
    && mkdir -p /app/media \
    && chown appuser /app/media
USER appuser

EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "2"]
