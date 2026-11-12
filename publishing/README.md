# publishing: sending approved posts to social accounts

| File | What it does |
|---|---|
| `admin.py` | Shows publications on the admin site. |
| `apps.py` | Tells Django this app exists. |
| `models.py` | `Publication`: one post version sent to one account, with a unique `idempotency_key`. |
| `serializers.py` | What a publication looks like inside a post. |
| `services.py` | `publish_post` (publish to every active account of the plan), `publish_to_account`, `add_ai_label`. |
| `tasks.py` | `publish_post_task`, the background job started when a post is approved. |

**Never posting twice:** the same post, version and account always give the
same `idempotency_key`, and the key is unique in the database. Only the
first attempt for a key contacts the platform. If a record already exists,
an earlier attempt may have reached the platform, and a missing post is
better than a duplicate one.

**The AI label:** `add_ai_label()` shortens the caption first and then adds
the label, so the label is never cut off by a platform's length limit.

**Partly failed:** if some accounts get the post and others fail, the post
is `published` and `status_reason` names the accounts that failed.
