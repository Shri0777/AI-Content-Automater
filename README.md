# AI Content Automator (V4 rebuild in progress)

A backend that finds high-quality news, writes social media posters with any
AI model you choose, reviews and corrects them, and posts them on a schedule.
It is a rebuild of an earlier version; see [plan.md](plan.md) for the plan and
progress.

**Status:** Phases 1 and 2 are built. The foundation (invite-only
accounts, cookie-based login, free-tier limits, in-app notifications, CI,
Docker) plus a **walking skeleton** of the whole product: save provider
keys, link a social account, create a plan, generate a post with a poster,
review it, approve it and publish it. Today that path runs on built-in
**fake providers** (demo mode). Real AI models, news sources and social
networks arrive in Phases 3, 4 and 6.

## Try the demo (no API keys needed)

You need Docker and Python 3.

```bash
docker compose up -d --build --wait
docker compose exec web python manage.py create_invite_codes 1
python3 scripts/demo_walkthrough.py --invite-code <the code printed above>
```

The script registers a user, saves demo keys, links a demo account, creates
a plan, makes a post (in the background worker), saves its poster to
`demo-poster.png`, approves it and checks it was published. CI runs these
same three commands on every push.

**Demo content is canned, not real AI output.** In demo mode, fake
providers (see [demo/](demo/README.md)) stand in for the AI models, the news
sources and the social network. Every article is fictional and links to
example.com, and every post is marked `demo_mode: true` in the API.

## Quickstart (development)

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
