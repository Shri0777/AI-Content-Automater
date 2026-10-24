# AI Content Automater V2 - Production Dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y postgresql-client gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/production.txt gunicorn

# Copy application
COPY . /app/

# Create non-root user and writable runtime/static directories
RUN useradd -m -u 1000 appuser && mkdir -p /app/staticfiles /app/media && chown -R appuser:appuser /app

# Collect static files with production settings before dropping privileges
RUN SECRET_KEY=build-only-placeholder DJANGO_SETTINGS_MODULE=content_automater.settings.development python manage.py collectstatic --noinput

USER appuser

EXPOSE 8000

CMD ["gunicorn", "content_automater.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
