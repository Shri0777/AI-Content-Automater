# studio: making posts

The studio turns a plan's topic into a finished post: it finds an article,
writes the caption, makes the poster, and has the post reviewed. Then the
post waits for the user's approval.

| File | What it does |
|---|---|
| `admin.py` | Shows posts, their versions and pipeline steps on the admin site. |
| `anthropic_text.py` | `AnthropicTextModel`: Claude through Anthropic's official library (the only file that uses it). Refuses to run without the user's own key, so the server's key can never be used by mistake. |
| `apps.py` | Tells Django this app exists. |
| `files.py` | `save_poster`, `read_poster`, `save_slide`, `read_slide`, `read_slides`, `save_artwork` and `read_artwork`: files in Django's file storage. The text-free artwork (when the plan asks for AI artwork) is kept so a corrected version reuses it. |
| `guards.py` | Prompt-injection defences: `neutralise_tags` (article text cannot close our `<article>` tags) and `leaked_instructions` (a post that repeats our instructions gets a blocker). |
| `image_models.py` | `ImageModel`, the base class every image provider follows. Providers only write `draw()`. |
| `image_providers.py` | `NvidiaFluxImageModel` and `FalImageModel`. |
| `model_outputs.py` | Serializers that check the text model's JSON answers, exactly like API input is checked. |
| `models.py` | `Post` (with `final_version()`: the best-reviewed version, used for showing and publishing), `PostVersion`, `Review` and `GenerationStep` (one row per stage run: the audit trail). |
| `fonts/` | Inter, the open-licence font all slide text is drawn in (licence in `fonts/OFL.txt`). |
| `openai_compatible.py` | Text and image models for any service that speaks OpenAI's format (OpenAI, OpenRouter, Groq, Gemini's compatible endpoint, Ollama and more). |
| `palette.py` | `palette_for`: turns a plan's brand colour into the slides' text, muted and accent colours, all passing WCAG AA contrast on that background. |
| `pipeline.py` | The stages `research` (the text model rates a shortlist of articles), `draft`, `make_poster` (draws the slides; asks an image model for cover artwork only if the plan turned it on), `review` and `correct` (at most 2 rounds, only while the score improves). `hand_over` then asks the auto-post gate: approve and publish, or wait for the owner. Each returns the AI models it used. |
| `post_rules.py` | Reads the writing rules from `post_creation.md` (between the `rules:start` and `rules:end` markers) for the draft and fix prompts; the prompt version includes a fingerprint of the rules. |
| `post_content.py` | `finished_post`: the text model's answer checked against the article in plain code (a quote must be word for word in the article and a figure must use its numbers, or they are dropped; text is shortened at a word). `layout_issues`: a "major" issue for each slide with too many words, which sends the post back for a rewrite. |
| `posters.py` | Drawing helpers shared by the slides: `font_of` (Inter, regular or bold), `wrap_text`, `fit_lines`, `fit_text`, `fit_artwork` and `draw_abstract_artwork`. |
| `public_links.py` | `make_public_poster_url` and `read_public_poster`: signed, login-free poster links that stop working after 7 days, for services that download images themselves (Buffer). |
| `prompts.py` | The versioned instructions sent to the text model. Article text is always wrapped in `<article>` tags and treated as untrusted. |
| `providers.py` | `get_text_model`, `get_image_model` and `get_provider`: the right provider class for a saved credential. |
| `retention.py` | `expire_old_images` (deletes poster, slide and artwork files after each user's retention days; the words stay) and `delete_old_steps` (pipeline records older than 90 days). |
| `reviewing.py` | `save_review` (the AI review plus our own checks: layout issues and leaked instructions) and `should_correct` (another round only while the score improves). |
| `runner.py` | `run_stage()`: runs the stage for a post's status, saves a `GenerationStep` (models, prompt versions, tokens) and handles each kind of failure. |
| `serializers.py` | What a post looks like in a list and in full detail. |
| `services.py` | `start_generation` (generate-now), `get_posts`, `get_post`, `approve_post` (a scheduled post then waits for its time), `edit_post` (the owner's own wording, as a new version on the same artwork), `reject_post`, `create_scheduled_post` (used by the dispatcher), `get_poster_bytes`, `get_slide_bytes`, and `queue_post_job` (fails the post with a clear message if background jobs are down). |
| `slide_parts.py` | The parts every slide is drawn with: `Deck` (the words and colours), `Frame`, `TextStyle`, `Row`, `make_row` (the biggest size that fits), `draw_centred` and `draw_footer`. Sizes are designed for 1080 pixels and scaled. |
| `slides.py` | The slide layouts (cover, figure with before-and-after bars, one per key point, quote, closing), `render_slides`, `render_share_image` (the one square image: the figure, else the cover) and `slides_to_pdf` (LinkedIn's document post). Only this file and `posters.py` use Pillow. Tested against reference images in `tests/golden/`. |
| `statuses.py` | `ALLOWED_TRANSITIONS`, the one table of allowed status changes; `change_status()`, which every change goes through; and `fail_after_crash()`. |
| `tasks.py` | `advance_post_task`: runs one stage, then queues the next. A busy provider is retried after 30, 60 and 120 seconds. If a bug crashes it, the post is marked `failed` and the error is raised again so it is logged. |
| `text_models.py` | `TextModel`, the base class every text provider follows (`score_articles`, `write_post`, `correct_post`, `write_image_prompt`, `review_post`). Providers only write `ask()`; prompting, reading and checking JSON, and one repair round live here. |
| `urls.py` | `/api/v1/plans/<id>/generate-now/`, `/api/v1/posts/...` (list, detail and `PATCH` to edit, `approve/`, `reject/`, `poster/`, `slides/<n>/`) and `/api/v1/public/posters/<signed link>.png`. |
| `verdicts.py` | `decide_verdict`: fixed rules turn the AI's scores and issues into pass, revise or reject; strict topics (layoffs, hiring, Linux tips) need perfect grounding and safety; a "major" issue from our own checks means revise. Six scores, including shareability. Tested over every combination of scores. |
| `visuals.py` | `save_visuals`: draws and saves a version's slides and share image in the plan's colours; used by the pipeline, corrections and the owner's edits. |
| `views.py` | Thin API classes. |

**A post's life:**

```
researching -> drafting -> imaging -> reviewing -> awaiting_approval
    |                                  correcting <-'   |          \        \
    |                                  (max 2 rounds)   |           \        \
 skipped (no good article)                       approved      rejected   expired (not approved in time)
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
