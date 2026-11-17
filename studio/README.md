# studio: making posts

The studio turns a plan's topic into a finished post: it finds an article,
writes the caption, makes the poster, and has the post reviewed. Then the
post waits for the user's approval.

| File | What it does |
|---|---|
| `admin.py` | Shows posts, their versions and pipeline steps on the admin site. |
| `anthropic_text.py` | `AnthropicTextModel`: Claude through Anthropic's official library (the only file that uses it). Refuses to run without the user's own key, so the server's key can never be used by mistake. |
| `apps.py` | Tells Django this app exists. |
| `files.py` | `save_poster` and `read_poster`: poster files in Django's file storage. |
| `image_models.py` | `ImageModel`, the base class every image provider follows. Providers only write `draw()`. |
| `image_providers.py` | `NvidiaFluxImageModel` and `FalImageModel`. |
| `model_outputs.py` | Serializers that check the text model's JSON answers, exactly like API input is checked. |
| `models.py` | `Post`, `PostVersion`, `Review` and `GenerationStep` (one row per stage run: the audit trail). |
| `openai_compatible.py` | Text and image models for any service that speaks OpenAI's format (OpenAI, OpenRouter, Groq, Gemini's compatible endpoint, Ollama and more). |
| `pipeline.py` | The stages `research`, `draft`, `make_poster` and `review`. Each returns the AI models it used. |
| `posters.py` | `render_poster` (crops any artwork to the poster size, then adds the headline and source) and `draw_abstract_artwork`. The only file that uses Pillow. |
| `public_links.py` | `make_public_poster_url` and `read_public_poster`: signed, login-free poster links that stop working after 7 days, for services that download images themselves (Buffer). |
| `prompts.py` | The versioned instructions sent to the text model. Article text is always wrapped in `<article>` tags and treated as untrusted. |
| `providers.py` | `get_text_model`, `get_image_model` and `get_provider`: the right provider class for a saved credential. |
| `runner.py` | `run_stage()`: runs the stage for a post's status, saves a `GenerationStep` (models, prompt versions, tokens) and handles each kind of failure. |
| `serializers.py` | What a post looks like in a list and in full detail. |
| `services.py` | `start_generation` (generate-now), `get_posts`, `get_post`, `approve_post`, `reject_post`, `get_poster_bytes`, and `queue_post_job` (fails the post with a clear message if background jobs are down). |
| `statuses.py` | `ALLOWED_TRANSITIONS`, the one table of allowed status changes; `change_status()`, which every change goes through; and `fail_after_crash()`. |
| `tasks.py` | `advance_post_task`: runs one stage, then queues the next. A busy provider is retried after 30, 60 and 120 seconds. If a bug crashes it, the post is marked `failed` and the error is raised again so it is logged. |
| `text_models.py` | `TextModel`, the base class every text provider follows. Providers only write `ask()`; prompting, reading and checking JSON, and one repair round live here. |
| `urls.py` | `/api/v1/plans/<id>/generate-now/`, `/api/v1/posts/...` (list, detail, `approve/`, `reject/`, `poster/`) and `/api/v1/public/posters/<signed link>.png`. |
| `verdicts.py` | `decide_verdict`: fixed rules turn the AI's scores and issues into pass, revise or reject. |
| `views.py` | Thin API classes. |

**A post's life:**

```
researching -> drafting -> imaging -> reviewing -> awaiting_approval
    |                                                   |          \
 skipped (no good article)                       approved      rejected
                                                     |
                                    publishing -> published (see publishing/)
any stage -> failed (a provider failed or a key is missing)
```

**Why one stage per job:** `advance_post_task` runs a single stage, then
queues itself again. Each stage checks whether its work is already saved
before doing it, so a crash only repeats the stage that was running, and
never makes anything twice.

**When a provider fails** (`studio/runner.py`):

| Error | Example | What happens |
|---|---|---|
| `ProviderBusy` | 429, 5xx, timeout | The stage is tried again later, up to 3 more times. Then the post fails. |
| `ProviderKeyRejected` | 401, 403 | The credential is marked `invalid`, the user is told, the post fails. No retry. |
| `ProviderError` | bad request, unreadable answer, refusal | The post fails with the reason. |

**A post never gets stuck.** Expected problems (a provider fails, a key is
missing) mark the post `failed` with a plain reason. A bug in a job, or a
queue that is down, does the same through `fail_after_crash()`. Each case
notifies the user. This guards against V3's worst failure, where posts sat
in a working status forever.

**The AI does not decide the verdict.** It gives scores and lists issues;
`decide_verdict()` applies fixed rules, so the same review always gets the
same verdict. Correction rounds arrive in Phase 7.
