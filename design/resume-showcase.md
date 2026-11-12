# Resume Showcase Plan

**Goal:** a "loud" portfolio project: something a recruiter or interviewer can understand in two minutes, run in three commands, and that holds up under deep technical questions.
Deployment is **deferred**. The showcase works locally with Docker Compose.
Related: [../plan.md](../plan.md), [system-design.md](system-design.md), [code-standard.md](code-standard.md).

**Rule for everything below:** claims are made only after they are true and measured. No invented numbers, users or traffic. If something is only verified against stubs, the README says so.

---

## 1. The story (real, and the strongest part)
> A previous version of this project looked complete (hundreds of passing tests) but failed on its first real runs. I diagnosed why (tests mocked the real paths, scope was too broad, wiring was never exercised), then redesigned and rebuilt it as a verified, scheduled, multi-provider AI content system.

Interviewers value engineers who can analyse a failure and fix the *process* as well as the code. The design documents already show this work.

## 2. What makes it loud (signals and where they live)
| Signal | Evidence in the repo |
|---|---|
| System design depth | `design/system-design.md`, 14 decision records, 5 FigJam diagrams |
| Correctness engineering | Database-claimed scheduler with leases, idempotent publishing, ambiguity handling, daylight-saving tests, race-condition tests |
| AI engineering | Bring-your-own-model keys (any text model), pluggable image models, structured outputs, AI review-and-correct loop, prompt-injection defence, an offline evaluation harness |
| Product thinking | Free-tier quotas, in-app notifications, auto-post versus manual approval with a closed-by-default safety gate |
| Security | Encrypted secrets, SSRF protection, owner-scoped data with an automated cross-user test, OAuth state and PKCE |
| Testing and CI | Real-wiring tests (real database, real worker, stub servers), CI badge, coverage on critical areas |
| **Unusual: a readability standard enforced by CI** | `design/code-standard.md` plus the checker script. Few portfolio projects can say "a beginner can read every file, and CI enforces it". |
| Documentation | `docs/CODE-TOUR.md`, per-app READMEs, a case study of the V3-to-V4 rebuild |

## 3. Demo mode: run everything with no API keys
Recruiters will not have your API keys. So the project ships a **demo mode** (ADR-014):
- `DEMO_MODE=true` swaps real providers for **built-in fakes**: a fake text model, a fake image model (Pillow-generated artwork), a fake news source with canned articles for each preset topic (jobs, layoffs, Linux tips, AI news), and a fake publisher that records posts in the database.
- A seeded demo user and a ready-made plan so the first request already shows something.
- `scripts/demo_walkthrough.py` runs the whole flow and prints each step: register, add credentials, create a plan, generate a post, review it, approve it, publish it.
- The interactive **Swagger UI** (`/docs/`) becomes the demo surface, since the frontend is built separately.
- Honesty: every demo response is labelled `demo_mode: true` in the API, and the README states plainly that demo content is canned, not real AI output. Switching to live mode needs real keys.
- The fakes are the **same stub servers the tests use**, so demo mode and CI share code and cannot drift apart.

## 4. Repository showcase checklist (Phase 10)
- [ ] README: one-paragraph pitch, architecture diagram, feature list, **three-command quickstart**, screenshot or short screen recording of the Swagger walkthrough, design-decision highlights, honest limitations, "what I would do next"
- [ ] Badges that are true: CI status, coverage (critical areas), Python and Django versions
- [ ] `docs/CODE-TOUR.md` and per-app READMEs up to date
- [ ] Diagrams exported into `docs/` (architecture, pipeline, lifecycle, data model)
- [ ] `docs/CASE-STUDY.md`: why V3 failed, what V4 changed, measured results
- [ ] Clean, meaningful commit history on the V4 branch (not "V1, V2, V3")
- [ ] `LICENSE`, `.env.example`, `CONTRIBUTING.md` (short)
- [ ] Optional: a 60 to 90 second screen recording of `scripts/demo_walkthrough.py`

## 5. Interview talking points (five stories, each backed by code and tests)
1. **From a failing app to a verified one:** what the old tests missed and how real-wiring tests fix it.
2. **Never post twice:** idempotency keys, the "ambiguous" publish state and why a missed post is better than a duplicate.
3. **Scheduling that survives crashes and daylight saving:** slots in the database, leases, named DST test cases.
4. **Free-tier quotas without races:** the conditional update and its concurrency test.
5. **Trustworthy automation:** the closed-by-default auto-post gate and AI review that is checked by code, not trusted blindly.
6. **Readable by design:** the beginner standard and why it makes the code maintainable and teachable.

## 6. Resume bullet templates (fill in only with measured results)
- "Designed and built a scheduled AI content platform (Django, Celery, PostgreSQL) that researches news, generates captions and poster images with any user-supplied model, reviews and corrects them with an AI reviewer, and publishes through Buffer and social-platform APIs."
- "Engineered a database-backed scheduler with idempotent publishing, verified by [N] concurrency and daylight-saving test cases with zero duplicate posts."
- "Replaced a failing prototype by diagnosing why [N] passing tests missed production failures; introduced real-wiring tests and CI gates, reaching [X]% branch coverage on critical modules."
- "Implemented per-user free-tier quotas with atomic counters, in-app notifications and invite-based registration."
- "Enforced a beginner-readable code standard in CI (function-length, complexity and import rules) across [N] modules."
Square-bracket values stay empty until we measure them. A bullet is dropped if its number cannot be measured.

## 7. What not to claim
- Real-world users, traffic, uptime or cost savings (none exist yet).
- Live integrations with LinkedIn, X, Meta or Buffer unless a human has actually run them with real credentials and recorded the result.
- That demo-mode output is real AI output.
