# studio: making posts

The studio turns a plan's topic into a finished post: it finds an article,
writes the caption, makes the poster, and has the post reviewed. Then the
post waits for the user's approval.

| File | What it does |
|---|---|
| `admin.py` | Shows posts, their versions and pipeline steps on the admin site. |
| `apps.py` | Tells Django this app exists. |
| `files.py` | `save_poster` and `read_poster`: poster files in Django's file storage. |
| `image_models.py` | `ImageModel`, the base class every image provider follows. |
| `models.py` | `Post`, `PostVersion`, `Review` and `GenerationStep` (one row per stage run: the audit trail). |
| `pipeline.py` | The stages `research`, `draft`, `make_poster` and `review`, and `run_stage()`, which runs the right one for a post's status. |
| `posters.py` | `render_poster` (headline and source on top of the artwork) and `draw_abstract_artwork`. The only file that uses Pillow. |
| `providers.py` | `get_text_model` and `get_image_model`: the right provider class for a saved credential. |
| `serializers.py` | What a post looks like in a list and in full detail. |
| `services.py` | `start_generation` (generate-now), `get_posts`, `get_post`, `approve_post`, `reject_post`, `get_poster_bytes`, and `queue_post_job` (fails the post with a clear message if background jobs are down). |
| `statuses.py` | `ALLOWED_TRANSITIONS`, the one table of allowed status changes; `change_status()`, which every change goes through; and `fail_after_crash()`. |
| `tasks.py` | `advance_post_task`: runs one stage, then queues the next. If a bug crashes it, the post is marked `failed` and the error is raised again so it is logged. |
| `text_models.py` | `TextModel`, the base class every text provider follows. |
| `urls.py` | `/api/v1/plans/<id>/generate-now/` and `/api/v1/posts/...` (list, detail, `approve/`, `reject/`, `poster/`). |
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

**A post never gets stuck.** Expected problems (a provider fails, a key is
missing) mark the post `failed` with a plain reason. A bug in a job, or a
queue that is down, does the same through `fail_after_crash()`. Each case
notifies the user. This guards against V3's worst failure, where posts sat
in a working status forever.

**The AI does not decide the verdict.** It gives scores and lists issues;
`decide_verdict()` applies fixed rules, so the same review always gets the
same verdict. Correction rounds arrive in Phase 7.
