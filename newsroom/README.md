# newsroom: finding articles worth posting about

Articles are read once into a shared store and used by every plan that
follows the same topic, so reading the news grows with **topics, not
users**. A plan never uses the same article twice, and when nothing is good
enough the post is **skipped**: we never post filler.

**Sources need no API keys:** each preset lists its sites' own RSS or Atom
feeds and a Hacker News search (`presets.py`). In demo mode the only source
is the canned, fictional one in `demo/`.

| File | What it does |
|---|---|
| `admin.py` | Shows stored articles on the admin site. |
| `apps.py` | Tells Django this app exists. |
| `budgets.py` | `use_request_budget`: a daily request cap per kind of source ("rss", "hackernews", "pages"), safe when workers race. |
| `extract.py` | `html_to_text`: readable text from HTML with Python's own parser (keeps `<article>` text, drops menus and scripts). |
| `feeds.py` | `parse_feed`: RSS 2.0 and Atom into article dicts, using defusedxml so hostile XML is refused. |
| `fetching.py` | Polite downloads: our User-Agent on every request, "only if changed" feed requests (ETag, Last-Modified), checked redirects, and pages read only where robots.txt allows us and the common AI crawlers. |
| `ingest.py` | `ingest_preset`, `ingest_active_presets` and `ensure_recent_ingest`: read sources into the store, skip the same story from other outlets, and read short articles' pages. |
| `models.py` | `Article`, `ArticleUse` (which plan used which article), `FeedState`, `SourceBudget` and `IngestRecord`. |
| `presets.py` | Loads the topic catalogue from `topics.json` (34 topics in 7 categories, each with feeds checked on 2026-11-17) and `get_preset`, which also builds users' own topics (`planning/custom_topics.py`). |
| `ranking.py` | The quality gates and ranking: fresh, unused, enough text, a cheap score, no repeated stories, then the AI's ratings. |
| `retention.py` | Clears article text after 14 days, deletes unused articles after 90 days and old daily request counts after 30. |
| `serializers.py` | An article inside a post, and in a preview. |
| `services.py` | `pick_article(plan, topic, text_model)`, `record_article_use` and `preview_topic`. |
| `sources.py` | `NewsSource` (the base class), `RssSource`, `HackerNewsSource` and `get_sources(preset)`. |
| `tasks.py` | `ingest_news_task`: every 30 minutes, reads the presets active plans follow. |
| `urls.py` | `/api/v1/news/preview/?preset=...` |
| `views.py` | Thin API class for the preview (counts towards a daily limit). |

**Choosing an article (`ranking.py`), gate by gate:**

1. Only the preset's own sources are read; each has a trust tier.
2. News must be inside the preset's freshness window (tips never go stale).
3. The plan has not used it before.
4. It has at least 280 characters of text, enough to write an accurate post.
5. A cheap score (tier, recency, length, topic words, popularity) picks a
   shortlist of 5, with only one copy of each story.
6. The plan owner's own text model rates the shortlist in one request;
   only an article rated relevant, credible and verifiable is chosen.

**Being a good citizen:** each kind of source has a daily request cap
(settings `NEWS_*_DAILY_CAP`); at the cap, plans use what is already stored.
Pages are only read where `robots.txt` allows our reader and does not block
AI crawlers; otherwise only the text the site's own feed publishes is used.
