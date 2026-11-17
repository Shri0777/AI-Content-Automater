"""Delete old article text and unused old articles (run nightly).

Article text is only working material: posts summarise and link to the
source. So the text is cleared after TEXT_RETENTION (the title, link and
source stay), and articles no plan ever used are deleted after
ARTICLE_RETENTION.
"""

from datetime import timedelta

from newsroom.models import Article, ArticleUse, SourceBudget

TEXT_RETENTION = timedelta(days=14)
ARTICLE_RETENTION = timedelta(days=90)
BUDGET_RETENTION = timedelta(days=30)


def clear_old_text(now):
    """Clear the text of articles stored before TEXT_RETENTION; return how many."""
    return (
        Article.objects.filter(stored_at__lt=now - TEXT_RETENTION)
        .exclude(text="")
        .update(text="", text_source="")
    )


def delete_old_unused_articles(now):
    """Delete articles older than ARTICLE_RETENTION that no plan used."""
    used = ArticleUse.objects.values("article_id")
    deleted, _ = (
        Article.objects.filter(stored_at__lt=now - ARTICLE_RETENTION)
        .exclude(id__in=used)
        .delete()
    )
    return deleted


def delete_old_budgets(now):
    """Delete daily request counts older than BUDGET_RETENTION."""
    deleted, _ = SourceBudget.objects.filter(
        day__lt=(now - BUDGET_RETENTION).date()
    ).delete()
    return deleted
