# newsroom: finding articles to post about

Articles are stored once and shared by everyone who follows the same topic.
A plan never uses the same article twice.

| File | What it does |
|---|---|
| `admin.py` | Shows stored articles on the admin site. |
| `apps.py` | Tells Django this app exists. |
| `models.py` | `Article` (stored once, found by a fingerprint of its address) and `ArticleUse` (which plan used which article). |
| `presets.py` | `TOPIC_PRESETS`: job hiring, layoffs, Linux tips and AI news, each with how fresh its articles must be. |
| `serializers.py` | The short version of an article shown inside a post. |
| `services.py` | `pick_article(plan, preset)`: read the sources, then return the newest fresh article the plan has not used (or `None`). Also `record_article_use`. |
| `sources.py` | `NewsSource`, the base class every news source follows (the adapter pattern). |

**Main flow:** the pipeline's research stage calls `pick_article()`. It
reads every source with `read_sources()` (a failing source is skipped),
saves what it finds with `save_articles()`, and filters out used and stale
articles. If nothing is left, the post is **skipped**: we never post filler.

**Today:** the only source is the demo one (canned, fictional articles).
Real keyless sources, RSS feeds and per-source daily budgets arrive in
Phase 6, and reading moves to a shared background job.
