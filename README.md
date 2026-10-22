# AI Content Automater V2

A Django application for researching, drafting, reviewing, and preparing content for Buffer publishing. The project uses Django templates, server-side workflows, PostgreSQL, and a shared responsive frontend module.

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

## Run The Application

```bash
python manage.py check
python manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/` and sign in. The root route is the authenticated dashboard. The shared `frontend` app supplies the shell, responsive navigation, dashboard, publishing overview, design tokens, CSS, and small progressive-enhancement JavaScript; content, research, providers, and publishing business rules remain in their existing Django apps.

Run the full verification suite with:

```bash
python manage.py makemigrations --check --dry-run
python -m compileall -q frontend content research ai_providers users content_automater
python manage.py test --keepdb --verbosity 1
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

## Current Capabilities

- Session-based registration, login, logout, and password reset.
- Owner-scoped content, versions, review, approval, and publishing preparation workflows.
- Research profiles, request snapshots, supported research collection, provenance, and result selection.
- Provider configuration with encrypted credentials, masking, validation, and existing HTMX status refreshes.
- Buffer-only publication and scheduling safeguards, including destination verification and ambiguity reconciliation.
- A responsive, accessible shared application interface for the implemented workflows.

## Deliberate Limitations

- Image generation, scheduling workers, Redis/Celery, deployment automation, and social providers beyond Buffer are outside the current application scope.
- Do not run provider validation, research collection, or publishing against real external accounts without appropriate credentials and authorization.
