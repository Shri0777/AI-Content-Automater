"""Collect and persist research using the connectors already supported by the app."""
import os

from django.utils import timezone
from django.db import transaction

from research.models import ContentCreationRequest, Research
from . import GNewsService, RankingService, RSSFeedService


class ResearchCollectionService:
    @staticmethod
    def collect(
        creation_request: ContentCreationRequest,
        rss_service_class=RSSFeedService,
        gnews_service_class=GNewsService,
        ranking_service_class=RankingService,
    ) -> dict:
        entries = []
        errors = []
        unsupported = sorted(set(creation_request.source_categories) - {'news'})
        if unsupported:
            errors.append('Not yet supported by an active connector: ' + ', '.join(unsupported))

        if 'news' in creation_request.source_categories:
            result = rss_service_class(timeout=10, max_entries=20).fetch_feed(
                'https://hnrss.org/newest', category='news'
            )
            if isinstance(result, dict) and result.get('error'):
                errors.append(f"RSS feed error: {result['error']}")
            elif isinstance(result, dict):
                entries.extend(result.get('entries') or [])

            api_key = os.getenv('GNEWS_API_KEY')
            if api_key:
                result = gnews_service_class(api_key=api_key, timeout=10).search(
                    query=creation_request.specific_query or ' '.join(creation_request.topics[:3]),
                    language=creation_request.language,
                    max_results=10,
                    days=creation_request.freshness_days,
                )
                if isinstance(result, dict) and result.get('error'):
                    errors.append(f"GNews error: {result['error']}")
                elif isinstance(result, dict):
                    entries.extend(result.get('entries') or [])
            else:
                errors.append('GNews API key not configured (optional)')

        ranked = ranking_service_class().deduplicate_and_rank(
            entries,
            query=creation_request.specific_query or '',
            topics=creation_request.topics,
            freshness_days=creation_request.freshness_days,
        )
        existing_urls = set(creation_request.research_results.values_list('canonical_url', flat=True))
        saved_count = len(existing_urls)
        with transaction.atomic():
            for entry in ranked[:50]:
                canonical_url = entry.get('canonical_url', entry['url'])
                if canonical_url in existing_urls:
                    continue
                Research.objects.create(
                    owner=creation_request.user,
                    creation_request=creation_request,
                    entry_type=entry.get('entry_type', 'rss'),
                    title=entry['title'],
                    summary=entry.get('summary', ''),
                    url=entry['url'],
                    canonical_url=canonical_url,
                    source_name=entry.get('source_name', 'Unknown'),
                    author=entry.get('author'),
                    published_date=entry.get('published_date'),
                    relevance_score=entry.get('relevance_score', 0.0),
                    freshness_score=entry.get('freshness_score', 0.0),
                    quality_score=entry.get('quality_score', 0.0),
                    overall_score=entry.get('overall_score', 0.0),
                    category=entry.get('category'),
                    ranking_rationale=entry.get('ranking_rationale', ''),
                )
                existing_urls.add(canonical_url)
                saved_count += 1

            creation_request.status = 'completed' if saved_count else 'failed'
            creation_request.error_message = '; '.join(errors) if errors else (None if saved_count else 'No research results found.')
            creation_request.error_type = ('partial_failure' if saved_count else 'no_results') if errors or not saved_count else None
            creation_request.completed_at = timezone.now()
            creation_request.save(update_fields=['status', 'error_message', 'error_type', 'completed_at', 'updated_at'])
        return {'success': saved_count > 0, 'saved_count': saved_count, 'errors': errors}
