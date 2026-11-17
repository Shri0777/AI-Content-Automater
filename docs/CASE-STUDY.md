# Case study: rebuilding a project that "passed" but did not work

## The problem

Version 3 of AI Content Automator looked finished. It had **428 test
functions** across **22,147 lines of Python** (measured from the
`legacy-v3` git tag, migrations excluded) and **85 Markdown documents**.
Yet it failed on its first real runs. The review recorded in
[plan.md](../plan.md) §1 found:

- a template that crashed and an undefined variable on real paths;
- retries that stayed stuck in `queued` forever;
- scheduled (Celery Beat) jobs that pointed at tasks that were never
  registered, so they silently never ran;
- one global Buffer token shared by every user;
- about 1,400 lines of publishers nothing used, a reconcile task that did
  nothing, and a dead app.

Its last push also failed CI (GitHub Actions, 2026-10-25).

**Why the tests missed it:** they mocked the very paths that broke. A test
that replaces the scheduler, the worker and the platform with mocks proves
that the mocks work.

## What changed in version 4

**1. Build the thinnest working path first.** Phase 2 was a "walking
skeleton": register → save keys → link an account → plan → generate →
poster → review → approve → publish, end to end, with fake providers. Every
later phase deepened one part of a path that already ran.

**2. Test the real wiring.** Tests use a real PostgreSQL database, real
threads for race conditions, and a real HTTP **stub server** that answers in
each provider's documented format (OpenAI-compatible, Anthropic, X,
LinkedIn, Meta, Buffer, RSS). A test of `publish()` sends real HTTP.

**3. Each phase had exit criteria, and each was proven.** For example,
"daylight-saving cases by name", "two dispatchers racing", "two workers
publishing at once make one call", "the auto-post gate as an exhaustive
table". After the tests, the real Docker stack was run end to end.

**4. Readable on purpose.** A beginner-readable standard
([design/code-standard.md](../design/code-standard.md)) is enforced in CI:
function length, file length, complexity, argument counts, no `lambda`,
generators or star-arguments, banned imports. **239 files** pass it.

**5. Honest by default.** A demo mode runs everything with no API keys and
labels its output as canned. Nothing is claimed as working with a real
platform until someone has run it with real credentials.

## Bugs version 4's own checks caught (and fixed)

These were found by tests or live runs during the rebuild, not by users:

| Found by | Bug | Fix |
|---|---|---|
| Two-thread publishing test | A worker that saw another still sending marked the whole post `failed`, though it went out on X. Another crashed on a status change the first had made. | The sending worker finishes the post; a stuck send becomes "unconfirmed" after 10 minutes. |
| Load test (100 posts) | The dispatcher started at most 50 posts a minute, so half a burst waited an extra minute. | One run claims batch after batch for up to 45 s. |
| Poster reference images | Landscape headlines ran into the source line; portrait text crossed the bottom margin. | Lines that fit are measured, the source line height is measured, not guessed. |
| Live news run | Layoffs had 0 usable articles (one-line feeds, pages closed to AI readers). A feed shared by two topics gave the second nothing new and filed stories under the wrong topic. | Full-text feeds filtered by topic; feed state and articles stored per topic. |
| Security review | A stolen 15-minute login token could make new recovery codes and take the account over for good. | New codes need the password again. |
| Live demo run | Demo mode could post about real articles left in the database by a live run. | Articles carry an `is_demo` flag; demo and live selection never mix. |
| Prompt-injection fixtures | `</article>` inside an article could close our untrusted-text block. | Tags are defused; a post that repeats our instructions can never pass review. |

## Results (measured on 2026-11-17)

| | V3 | V4 |
|---|---|---|
| Python, excluding migrations | 22,147 lines | 10,444 app lines (+6,936 test lines) |
| Tests | 428 functions; did not catch the failures above | 475 tests, about 30 s, real database and HTTP |
| Branch coverage (app code) | not measured | **92%** overall, **96%** on the critical modules |
| CI | failing | lint, readability gate, security scan, dependency audit, deploy check, schema check, tests with a 90% coverage floor |
| Load (local Docker, fake providers) | not measured | 100 due posts ready in 30 s; 400 in 56 s; 0 failures |

The load numbers measure the scheduler and database, not AI speed: the fake
providers answer in milliseconds.

## What I would do differently from the start

- Run the real stack end to end on day one, before writing any feature.
- Put concurrency tests next to any code that "claims" work, because the
  worst bugs above only appear with two workers at once.
- Treat live runs as tests: the stubs proved the code, the live run proved
  the assumptions (which feeds have text, which sites allow AI readers).
