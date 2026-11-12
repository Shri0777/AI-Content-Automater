# AI Content Automator (V4 rebuild in progress)

A backend that finds high-quality news, writes social media posters with any
AI model you choose, reviews and corrects them, and posts them on a schedule.
It is a rebuild of an earlier version; see [plan.md](plan.md) for the plan and
progress.

**Status:** Phase 1 (foundation) is being built: accounts with invite-only
registration, cookie-based login, free-tier limits, in-app notifications,
CI and Docker. The content pipeline itself arrives in later phases.

## Quickstart

You need [uv](https://docs.astral.sh/uv/) and Docker.

```bash
uv sync                                 # install the exact package versions
docker compose up -d db redis           # Postgres on 5433, Redis on 6380
uv run python manage.py migrate         # create the database tables
uv run python manage.py create_invite_codes 1
uv run python manage.py runserver
```

Then open http://localhost:8000/api/v1/docs/ to explore the API.

**Prefer pip?** `requirements.txt` lists the same exact versions (production
packages only), generated from `uv.lock`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

After changing dependencies with `uv add` or `uv remove`, regenerate it:

```bash
uv export --frozen --no-dev --no-hashes --no-emit-project --format requirements-txt -o requirements.txt
```

To run everything in Docker instead (web server, worker and scheduler):

```bash
docker compose up --build
```

## Checks

```bash
uv run pytest                           # tests
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_readability.py   # beginner-readable code rules
docker compose run --rm worker python scripts/smoke_check.py
```

## Where to start reading

1. [docs/CODE-TOUR.md](docs/CODE-TOUR.md): a guided path through the code.
2. [plan.md](plan.md): what is being built, in which order.
3. [design/](design/): system design, decision records, test strategy and the
   [code standard](design/code-standard.md) that keeps every file readable by
   a beginner.

The previous version (V3) is preserved under the git tag `legacy-v3`.
