# AI Content Automator (V4 rebuild in progress)

A backend that finds high-quality news, writes social media posters with any
AI model you choose, reviews and corrects them, and posts them on a schedule.
It is a rebuild of an earlier version; see [plan.md](plan.md) for the plan and
progress.

**Status:** Phases 1 and 2 are built. The foundation (invite-only
accounts, cookie-based login, free-tier limits, in-app notifications, CI,
Docker) plus a **walking skeleton** of the whole product: save provider
keys, link a social account, create a plan, generate a post with a poster,
review it, approve it and publish it. Phase 3 adds real AI providers:
Claude, any OpenAI-compatible service (OpenAI, OpenRouter, Groq, Gemini,
Ollama and more), and NVIDIA FLUX or fal for images, with "test connection",
retries and an SSRF-safe web client. These are tested against stub servers
that answer in each provider's documented format; they have **not yet been
run with real keys**. Real news sources and social networks arrive in
Phases 4 and 6.

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

## Linking real social accounts

Demo mode needs nothing. To link real accounts, set these environment
variables (`GET /api/v1/social/platforms/` shows which platforms are ready):

| Variable | Needed for |
|---|---|
| `PUBLIC_API_URL` | The address the internet uses to reach this API (default `http://localhost:8000`). Platforms send users back here, and Buffer downloads posters from here, so Buffer needs a public address. |
| `FRONTEND_URL` | Where users land after linking (default `http://localhost:5173`). |
| `X_CLIENT_ID`, `X_CLIENT_SECRET` | X: an app from the X developer console with OAuth 2.0 turned on. |
| `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` | LinkedIn: an app with the "Share on LinkedIn" and "Sign In with LinkedIn using OpenID Connect" products. |
| `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` | Facebook Pages: a Meta app with Facebook Login. Some permissions need Meta's app review. |
| `LINKEDIN_API_VERSION` | Optional; LinkedIn's API version, `YYYYMM` (default `202610`). |

Register each app's redirect address as
`<PUBLIC_API_URL>/api/v1/social/link/<x|linkedin|facebook>/callback/`.
Buffer needs no app: each user pastes their own API key from Buffer's
Settings > API page. The adapters are tested against stub servers that
answer in each platform's documented format; they have not yet been run
against the live platforms.

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
