# publishing: sending approved posts to social accounts

| File | What it does |
|---|---|
| `admin.py` | Shows publications on the admin site. |
| `apps.py` | Tells Django this app exists. |
| `models.py` | `Publication`: one post version sent to one account, with a unique `idempotency_key`. |
| `serializers.py` | What a publication looks like inside a post. |
| `captions.py` | `fitted_caption`: the whole caption where it fits; for a short limit (X's 280 characters) a caption rebuilt from the headline, takeaway, closing question and link instead of one cut mid-sentence. |
| `gate.py` | The auto-post gate: `check_auto_post(plan, topic, review)`, five small rules, closed by default. Tested as a table, one row per case. |
| `reconcile.py` | Settles "ambiguous" publications (sent, never answered): asks the platform, otherwise asks the owner once; `resolve_publication` records the owner's answer. Sends stuck in "publishing" (a crashed worker) become ambiguous after 10 minutes. |
| `services.py` | `publish_post` (publish to every active account of the plan), `publish_to_account`, `finish_post` (settles the post's status; a second worker stops quietly), `add_ai_label`, and `images_of` (the share image plus, for LinkedIn, a PDF of the slides). |
| `scheduled.py` | `publish_due_posts` (approved scheduled posts, at their time) and `expire_late_approvals` (posts nobody approved in time, for plans set to `expire`). Both run every minute with the dispatcher. |
| `tasks.py` | `publish_post_task` (publishes one post) and `reconcile_publications_task` (every 10 minutes). |
| `urls.py` | `/api/v1/publications/<id>/resolve/` |
| `views.py` | Thin API class for the owner's answer about an unconfirmed post. |

**Never posting twice:** the same post, version and account always give the
same `idempotency_key`, and the key is unique in the database. Only the
first attempt for a key contacts the platform. If a record already exists,
an earlier attempt may have reached the platform, and a missing post is
better than a duplicate one.

**Sent, but no answer ("ambiguous"):** if a platform takes the request and
then never answers, the post may or may not be live. It is never sent
again automatically: a duplicate is worse than a missing post. The
publication is marked `ambiguous`, reconcile asks the platform, and if the
platform cannot say, the owner is asked to check and answer. A refused
connection (nothing was sent) is an ordinary failure instead.

**When posts go out:** a "generate now" post is published as soon as it is
approved. A scheduled post that is approved early waits for its slot's
`publish_at`. If nobody approves it by `publish_at` plus the plan's
`max_lateness_minutes`, it is `expired` (plan setting `expire`, the default)
or kept until approved and then published at once (`hold`).

**The AI label:** `add_ai_label()` shortens the caption first and then adds
the label, so the label is never cut off by a platform's length limit.

**Partly failed:** if some accounts get the post and others fail, the post
is `published` and `status_reason` names the accounts that failed.
