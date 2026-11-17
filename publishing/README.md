# publishing: sending approved posts to social accounts

| File | What it does |
|---|---|
| `admin.py` | Shows publications on the admin site. |
| `apps.py` | Tells Django this app exists. |
| `models.py` | `Publication`: one post version sent to one account, with a unique `idempotency_key`. |
| `serializers.py` | What a publication looks like inside a post. |
| `services.py` | `publish_post` (publish to every active account of the plan), `publish_to_account`, `add_ai_label`. |
| `scheduled.py` | `publish_due_posts` (approved scheduled posts, at their time) and `expire_late_approvals` (posts nobody approved in time, for plans set to `expire`). Both run every minute with the dispatcher. |
| `tasks.py` | `publish_post_task`, the background job that publishes one post. |

**Never posting twice:** the same post, version and account always give the
same `idempotency_key`, and the key is unique in the database. Only the
first attempt for a key contacts the platform. If a record already exists,
an earlier attempt may have reached the platform, and a missing post is
better than a duplicate one.

**When posts go out:** a "generate now" post is published as soon as it is
approved. A scheduled post that is approved early waits for its slot's
`publish_at`. If nobody approves it by `publish_at` plus the plan's
`max_lateness_minutes`, it is `expired` (plan setting `expire`, the default)
or kept until approved and then published at once (`hold`).

**The AI label:** `add_ai_label()` shortens the caption first and then adds
the label, so the label is never cut off by a platform's length limit.

**Partly failed:** if some accounts get the post and others fail, the post
is `published` and `status_reason` names the accounts that failed.
