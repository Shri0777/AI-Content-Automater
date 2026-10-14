# AI Content Automater V2

Django foundation for the AI Content Automater V2 project.

This repository is currently at Iteration 0: project infrastructure only. It does not yet include authentication, content models, AI integrations, publishing, scheduling, Celery, Redis, Docker, or business APIs.

## Prerequisites

- Python 3.12 for the approved Django 5.1 dependency set.
- PostgreSQL running locally.
- Git.

The default shell Python on this machine is Python 3.14, but Django 5.1 is officially supported on Python 3.10 through 3.13. Use `python3.12` for the local virtual environment unless the approved dependency set changes.

## Setup

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/development.txt
cp .env.example .env
```

Generate a development secret key and place it in `.env`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Create the development database if it does not already exist:

```bash
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -c "CREATE DATABASE ai_content_automater_dev;"
```

Run migrations:

```bash
python manage.py migrate
```

## Verification

```bash
python manage.py check
python manage.py showmigrations
python manage.py runserver 127.0.0.1:8000
curl -i http://127.0.0.1:8000/
```

Expected root response:

```text
AI Content Automater foundation is running.
```

## Configuration

Development settings are selected by default in `manage.py`, `content_automater/asgi.py`, and `content_automater/wsgi.py`:

```text
content_automater.settings.development
```

Production settings must be selected explicitly:

```bash
DJANGO_SETTINGS_MODULE=content_automater.settings.production python manage.py check
```

Production settings do not load the local `.env` file and require explicit environment variables for `SECRET_KEY`, `ALLOWED_HOSTS`, and database connection values.

## Security Notes

- `.env` is ignored by Git and must not be committed.
- `.env.example` contains placeholders only.
- Database credentials are read from environment variables.
- `DEBUG` is forced on only in development settings and forced off in production settings.
- No real secrets are stored in source files.

## Current Scope

Implemented:

- Django project package: `content_automater`
- Split settings: `base`, `development`, `production`
- PostgreSQL configuration
- Django default migrations
- Minimal root status endpoint
- Dependency manifests
- Environment template
- Local setup documentation

Deferred:

- Custom user model and authentication workflows
- Content and workflow domain models
- AI, research, publishing, scheduling, and campaign features
- Celery/Redis
- Docker and CI/CD
- Production deployment hardening
