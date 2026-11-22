"""The plain-code checks on what the text model wrote: quotes must be word for
word in the article, figures must use its numbers, and slides with too many
words send the post back for a rewrite."""

from types import SimpleNamespace

from demo.text_model import DemoTextModel
from studio.models import Post, Review
from studio.post_content import (
    finished_post,
    grounded_figure,
    grounded_quote,
    layout_issues,
    trim_words,
)
from studio.tasks import advance_post_task

ARTICLE_TEXT = (
    "Contoso cut its API price from $2.50 to $1.25 per million tokens, a 50% "
    "drop. “Long documents should be cheap to read for everyone,” "
    "said Ada Lovelace, head of product. The change starts on 1,200 accounts."
)
ARTICLE = SimpleNamespace(
    url="https://example.com/a",
    source_name="Example News",
    title="Contoso halves its API price",
    text=ARTICLE_TEXT,
)


def model_answer(changes=None):
    """Return a well-formed draft answer, with some fields changed."""
    answer = {
        "headline": "Contoso halves its API price",
        "points": ["Input tokens now cost $1.25 per million, down from $2.50."],
        "figure": {"value": "50%", "label": "cheaper per token", "compare": None},
        "quote": {
            "text": "Long documents should be cheap to read for everyone",
            "speaker": "Ada Lovelace, head of product",
        },
        "takeaway": "Long prompts cost half as much.",
        "caption": "Why it matters.",
    }
    answer.update(changes or {})
    return answer


def test_a_quote_copied_from_the_article_is_kept():
    quote = grounded_quote(model_answer()["quote"], ARTICLE_TEXT)

    assert quote["speaker"] == "Ada Lovelace, head of product"


def test_a_quote_that_is_not_in_the_article_is_dropped():
    made_up = {"text": "We will cut prices again next year for sure", "speaker": "Ada"}
    wrong_speaker = {
        "text": "Long documents should be cheap to read for everyone",
        "speaker": "Grace Hopper",
    }

    assert grounded_quote(made_up, ARTICLE_TEXT) == {}
    assert grounded_quote(wrong_speaker, ARTICLE_TEXT) == {}
    assert grounded_quote({"text": "cheap to read", "speaker": ""}, ARTICLE_TEXT) == {}


def test_a_figure_must_use_the_articles_own_numbers():
    kept = grounded_figure({"value": "1,200", "label": "accounts"}, ARTICLE_TEXT)

    assert kept["value"] == "1,200"
    assert grounded_figure({"value": "75%", "label": "x"}, ARTICLE_TEXT) == {}
    assert grounded_figure({"value": "half", "label": "x"}, ARTICLE_TEXT) == {}


def test_comparison_bars_are_kept_only_when_both_numbers_are_in_the_article():
    bars = [
        {"label": "Before", "amount": 2.5, "display": "$2.50"},
        {"label": "After", "amount": 1.25, "display": "$1.25"},
    ]
    invented = [bars[0], {"label": "After", "amount": 1.0, "display": "$1.00"}]

    figure = {"value": "50%", "label": "cheaper", "compare": bars}
    assert len(grounded_figure(figure, ARTICLE_TEXT)["compare"]) == 2
    figure["compare"] = invented
    assert grounded_figure(figure, ARTICLE_TEXT)["compare"] == []


def test_the_finished_post_drops_what_the_article_does_not_support():
    answer = model_answer({"figure": {"value": "90%", "label": "x"}, "quote": None})

    finished = finished_post(answer, ARTICLE)

    assert finished["figure"] == {}
    assert finished["quote"] == {}
    assert finished["takeaway"] == "Long prompts cost half as much."
    assert finished["caption"].endswith("Source: Example News, https://example.com/a")


def test_long_text_is_shortened_at_a_word_never_inside_one():
    shortened = trim_words("Contoso halves its API price for everyone today", 25)

    assert shortened == "Contoso halves its API…"
    assert trim_words("Short", 25) == "Short"


def test_slides_with_too_many_words_are_major_issues():
    version = SimpleNamespace(
        headline="A headline that is far too long to read on a cover at a glance",
        points=["Short and fine.", "word " * 40],
        figure={"value": "1,234,567,890 dollars"},
        takeaway="fine",
    )

    issues = layout_issues(version)

    assert [issue["severity"] for issue in issues] == ["major"] * 3
    assert "Key point 2" in issues[1]["problem"]


def test_a_well_sized_post_has_no_layout_issues():
    version = SimpleNamespace(
        headline="Contoso halves its API price",
        points=["Input tokens now cost $1.25 per million, down from $2.50."],
        figure={"value": "50%"},
        takeaway="Long prompts cost half as much.",
    )

    assert layout_issues(version) == []


def test_a_wordy_slide_sends_the_post_back_for_a_rewrite(plan, monkeypatch):
    real_write = DemoTextModel.write_post
    rewrites = []

    def wordy_write(self, article, requirements):
        written = real_write(self, article, requirements)
        written["points"] = written["points"][:1] + ["too many words " * 15]
        return written

    def shorter_rewrite(self, article, requirements, version, issues):
        rewrites.append(issues)
        return real_write(self, article, requirements)

    monkeypatch.setattr(DemoTextModel, "write_post", wordy_write)
    monkeypatch.setattr(DemoTextModel, "correct_post", shorter_rewrite)

    post = Post.objects.create(user=plan.user, plan=plan, topic=plan.topics.first())
    advance_post_task.delay(str(post.id))
    post.refresh_from_db()

    first = Review.objects.get(version__post=post, version__number=1)
    assert first.verdict == "revise"
    assert rewrites[0][0]["severity"] == "major"
    assert post.final_version().number == 2
    assert post.status == "awaiting_approval"
