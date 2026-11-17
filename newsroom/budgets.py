"""A daily request cap for each kind of news source, shared by all users.

Reading the news is paid for by the operator (in bandwidth and in goodwill
with the sites we read), so each kind of source ("rss", "hackernews",
"pages") may make at most NEWS_DAILY_REQUEST_CAPS requests per UTC day.
"""

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from newsroom.models import SourceBudget


def use_request_budget(source):
    """Count one request for source; return False if today's cap is reached.

    The count only goes up while it is below the cap, in one UPDATE, so two
    workers asking at the same moment can never pass the cap together.
    """
    cap = settings.NEWS_DAILY_REQUEST_CAPS[source]
    budget, _ = SourceBudget.objects.get_or_create(
        source=source, day=timezone.now().date()
    )
    updated = SourceBudget.objects.filter(id=budget.id, used__lt=cap).update(
        used=F("used") + 1
    )
    return updated == 1


def requests_used_today(source):
    """Return how many requests source has made today."""
    budget = SourceBudget.objects.filter(
        source=source, day=timezone.now().date()
    ).first()
    if budget is None:
        return 0
    return budget.used
