# demo: fake providers, so everything runs with no API keys

When `DEMO_MODE` is on (the default in development and tests), these fakes
stand in for every outside service. They are subclasses of the same base
classes the real providers use, so the rest of the code runs exactly the
same either way. Nothing here uses the internet.

**Everything they make is canned, not real AI output.** Posts made in demo
mode are marked `demo_mode: true` in the API.

| File | What it does |
|---|---|
| `articles.py` | `DEMO_ARTICLES`: three invented articles for each topic preset, each long enough to pass the newsroom's text gate. Every company and link is fictional (links use example.com). |
| `image_model.py` | `DemoImageModel`: draws gradient-and-circle artwork with `draw_abstract_artwork()`. |
| `news_source.py` | `DemoNewsSource`: returns the canned articles, dated a few hours ago. |
| `publisher.py` | `DemoPublisher`: pretends to publish and returns a made-up post id. |
| `text_model.py` | `DemoTextModel`: rates every shortlisted article the same, and fills in templates for the caption, image prompt and review. Its review flags a caption that does not link to its source. |

The tests use these same fakes, so demo mode and the tests cannot drift
apart.
