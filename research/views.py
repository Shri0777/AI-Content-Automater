"""
Research views for profile management and research execution.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import os
import logging
from django.utils import timezone
from django.db import transaction

from research.models import ResearchProfile, ContentCreationRequest, Research
from research.services import RSSFeedService, GNewsService, RankingService
from content.models import Content

logger = logging.getLogger(__name__)

RESEARCH_CATEGORIES = [
    ('documentation', 'Official Documentation & Blogs'),
    ('news', 'News/RSS'),
    ('blogs', 'Developer Blogs'),
    ('research_papers', 'Research Papers'),
    ('videos', 'Videos & Creators'),
    ('social', 'Social Discussions'),
    ('government', 'Government & Primary Data'),
]


def _request_form_context(profile, values=None):
    """Build a render context that preserves a failed request submission."""
    values = values or {}
    selected_categories = values.getlist('source_categories') if values else profile.source_categories
    return {
        'profile': profile,
        'topics_str': values.get('topics', ', '.join(profile.topics)) if values else ', '.join(profile.topics),
        'submitted_values': values,
        'selected_categories': selected_categories,
        'available_categories': RESEARCH_CATEGORIES,
    }


@login_required
def profile_view(request):
    """
    Display user's research profile (saved defaults).
    """
    profile = ResearchProfile.get_or_create_for_user(request.user)
    
    context = {
        'profile': profile,
        'source_categories_display': ', '.join(profile.source_categories) if profile.source_categories else 'None',
        'topics_display': ', '.join(profile.topics) if profile.topics else 'None',
    }
    
    return render(request, 'research/profile_view.html', context)


@login_required
def profile_edit(request):
    """
    Edit research profile (saved defaults).
    """
    profile = ResearchProfile.get_or_create_for_user(request.user)
    
    if request.method == 'POST':
        # Extract form data
        topics_str = request.POST.get('topics', '').strip()
        topics = [t.strip() for t in topics_str.split(',') if t.strip()]
        
        audience = request.POST.get('audience', '').strip()
        content_goal = request.POST.get('content_goal', '').strip()
        
        try:
            freshness_days = int(request.POST.get('freshness_days', 7))
        except (ValueError, TypeError):
            freshness_days = 7
        
        allow_older_sources = request.POST.get('allow_older_sources') == 'on'
        language = request.POST.get('language', 'en').strip()
        
        # Source categories (checkboxes)
        source_categories = request.POST.getlist('source_categories')
        
        # Validate
        if not topics:
            messages.error(request, 'At least one topic is required.')
            return render(request, 'research/profile_edit.html', {'profile': profile})
        
        if not audience:
            messages.error(request, 'Audience is required.')
            return render(request, 'research/profile_edit.html', {'profile': profile})
        
        if freshness_days < 1:
            messages.error(request, 'Freshness days must be at least 1.')
            return render(request, 'research/profile_edit.html', {'profile': profile})
        
        # Update profile
        profile.topics = topics
        profile.audience = audience
        profile.content_goal = content_goal
        profile.freshness_days = freshness_days
        profile.allow_older_sources = allow_older_sources
        profile.language = language
        profile.source_categories = source_categories
        profile.save()
        
        messages.success(request, 'Research profile updated successfully.')
        return redirect('research:profile_view')
    
    # GET request - display form
    context = {
        'profile': profile,
        'topics_str': ', '.join(profile.topics) if profile.topics else '',
        'available_categories': [
            ('documentation', 'Official Documentation & Blogs'),
            ('news', 'News/RSS'),
            ('blogs', 'Developer Blogs'),
            ('research_papers', 'Research Papers'),
            ('videos', 'Videos & Creators'),
            ('social', 'Social Discussions'),
            ('government', 'Government & Primary Data'),
        ]
    }
    
    return render(request, 'research/profile_edit.html', context)


@login_required
def request_new(request):
    """
    Create new content creation request.
    Pre-populated with profile defaults, allows overrides.
    """
    profile = ResearchProfile.get_or_create_for_user(request.user)
    
    if request.method == 'POST':
        # Extract form data (similar to profile edit)
        topics_str = request.POST.get('topics', '').strip()
        topics = [t.strip() for t in topics_str.split(',') if t.strip()]
        
        audience = request.POST.get('audience', '').strip()
        content_goal = request.POST.get('content_goal', '').strip()
        
        try:
            freshness_days = int(request.POST.get('freshness_days', 7))
        except (ValueError, TypeError):
            freshness_days = 7
        
        allow_older_sources = request.POST.get('allow_older_sources') == 'on'
        language = request.POST.get('language', 'en').strip()
        source_categories = request.POST.getlist('source_categories')
        specific_query = request.POST.get('specific_query', '').strip()
        
        # Validate
        if not topics:
            messages.error(request, 'At least one topic is required.')
            return render(request, 'research/request_new.html', _request_form_context(profile, request.POST))
        
        # Create request with overrides
        overrides = {
            'topics': topics,
            'audience': audience,
            'content_goal': content_goal,
            'freshness_days': freshness_days,
            'allow_older_sources': allow_older_sources,
            'language': language,
            'source_categories': source_categories,
            'specific_query': specific_query,
        }
        
        creation_request = ContentCreationRequest.create_from_profile(
            user=request.user,
            overrides=overrides
        )
        
        messages.success(request, 'Research request created. Review settings before executing.')
        return redirect('research:request_detail', pk=creation_request.pk)
    
    # GET - display form pre-populated from profile
    context = _request_form_context(profile)
    
    return render(request, 'research/request_new.html', context)


@login_required
def request_detail(request, pk):
    """
    Display content creation request details.
    Shows effective settings (snapshot) for this request.
    """
    creation_request = get_object_or_404(
        ContentCreationRequest,
        pk=pk,
        user=request.user
    )
    
    # Get research results if any
    research_results = Research.objects.filter(
        creation_request=creation_request,
        owner=request.user
    ).order_by('-overall_score')
    
    context = {
        'request': creation_request,
        'research_results': research_results,
        'topics_display': ', '.join(creation_request.topics) if creation_request.topics else 'None',
        'categories_display': ', '.join(creation_request.source_categories) if creation_request.source_categories else 'None',
        'selected_count': research_results.filter(is_selected=True).count(),
        'excluded_count': research_results.filter(is_excluded=True).count(),
    }
    
    return render(request, 'research/request_detail.html', context)


@login_required
@require_http_methods(["POST"])
def request_execute(request, pk):
    """
    Execute research for a content creation request.
    Calls RSS and GNews services, ranks results, saves to database.
    """
    creation_request = get_object_or_404(
        ContentCreationRequest,
        pk=pk,
        user=request.user
    )
    
    # Serialize duplicate submissions for the same request. A second request must
    # not launch another batch while the first is still gathering sources.
    with transaction.atomic():
        creation_request = ContentCreationRequest.objects.select_for_update().get(
            pk=pk, user=request.user
        )
        if creation_request.status == 'researching':
            messages.info(request, 'Research is already running for this request.')
            return redirect('research:request_detail', pk=creation_request.pk)
        creation_request.status = 'researching'
        creation_request.error_message = None
        creation_request.error_type = None
        creation_request.completed_at = None
        creation_request.save(update_fields=['status', 'error_message', 'error_type', 'completed_at'])
    
    try:
        # Gather entries from implemented sources only; do not imply that unimplemented
        # categories are being searched.
        all_entries = []
        errors = []
        implemented_categories = {'news'}
        unsupported_categories = sorted(set(creation_request.source_categories) - implemented_categories)
        if unsupported_categories:
            errors.append('Not yet supported by an active connector: ' + ', '.join(unsupported_categories))
        
        # RSS/Atom feeds (example feeds - in production, these would be configurable)
        rss_service = RSSFeedService(timeout=10, max_entries=20)
        
        # Example tech RSS feeds
        rss_feeds = [
            ('https://hnrss.org/newest', 'news'),
            # Add more feeds based on topics/categories
        ]
        
        for feed_url, category in rss_feeds:
            if category in creation_request.source_categories:
                result = rss_service.fetch_feed(feed_url, category=category)
                if not isinstance(result, dict):
                    result = {}
                error = result.get('error')
                if error:
                    errors.append(f"RSS feed error: {error}")
                else:
                    all_entries.extend(result.get('entries') or [])
        
        # GNews
        if 'news' in creation_request.source_categories:
            gnews_api_key = os.getenv('GNEWS_API_KEY')
            if gnews_api_key:
                gnews_service = GNewsService(api_key=gnews_api_key, timeout=10)
                
                # Build search query from topics
                query = ' '.join(creation_request.topics[:3])  # Use first 3 topics
                if creation_request.specific_query:
                    query = creation_request.specific_query
                
                result = gnews_service.search(
                    query=query,
                    language=creation_request.language,
                    max_results=10,
                    days=creation_request.freshness_days
                )
                
                if not isinstance(result, dict):
                    result = {}
                error = result.get('error')
                if error:
                    errors.append(f"GNews error: {error}")
                else:
                    all_entries.extend(result.get('entries') or [])
            else:
                errors.append("GNews API key not configured (optional)")
        
        # Rank and deduplicate
        ranking_service = RankingService()
        ranked_entries = ranking_service.deduplicate_and_rank(
            all_entries,
            query=creation_request.specific_query or '',
            topics=creation_request.topics,
            freshness_days=creation_request.freshness_days
        )
        
        # Save to database
        saved_count = 0
        for entry in ranked_entries[:50]:  # Limit to top 50
            research = Research.objects.create(
                owner=request.user,
                creation_request=creation_request,
                entry_type=entry.get('entry_type', 'rss'),
                title=entry['title'],
                summary=entry.get('summary', ''),
                url=entry['url'],
                canonical_url=entry.get('canonical_url', entry['url']),
                source_name=entry.get('source_name', 'Unknown'),
                author=entry.get('author'),
                published_date=entry.get('published_date'),
                relevance_score=entry.get('relevance_score', 0.0),
                freshness_score=entry.get('freshness_score', 0.0),
                quality_score=entry.get('quality_score', 0.0),
                overall_score=entry.get('overall_score', 0.0),
                category=entry.get('category'),
                ranking_rationale=entry.get('ranking_rationale', '')
            )
            saved_count += 1
        
        # Update request status
        if saved_count > 0:
            creation_request.status = 'completed'
            if errors:
                creation_request.error_message = "; ".join(errors)
                creation_request.error_type = 'partial_failure'
            else:
                creation_request.error_message = None
                creation_request.error_type = None
        else:
            creation_request.status = 'failed'
            creation_request.error_message = "; ".join(errors) if errors else "No research results found."
            creation_request.error_type = 'no_results'

        creation_request.completed_at = timezone.now()
        creation_request.save()
        
        # Show results
        if saved_count > 0:
            msg = f'Research complete! Found and ranked {saved_count} sources.'
            if errors:
                msg += f' (Some sources had errors: {len(errors)})'
            messages.success(request, msg)
        else:
            messages.warning(request, 'Research completed but no results found. Try different topics or sources.')
        
        if errors and saved_count == 0:
            for error in errors[:3]:  # Show first 3 errors
                messages.error(request, error)
        
    except Exception as e:
        logger.exception('Research execution failed for request %s.', creation_request.pk)
        creation_request.status = 'failed'
        creation_request.error_type = 'execution_error'
        creation_request.error_message = 'Research execution failed. Check application logs for the internal error details.'
        creation_request.completed_at = timezone.now()
        creation_request.save(update_fields=['status', 'error_type', 'error_message', 'completed_at'])
        messages.error(request, creation_request.error_message)
    
    return redirect('research:request_detail', pk=creation_request.pk)


@login_required
@require_http_methods(["POST"])
def research_select(request, pk):
    """
    Toggle selection of a research item (HTMX endpoint).
    """
    research = get_object_or_404(Research, pk=pk, owner=request.user)
    
    action = request.POST.get('action', 'toggle')
    
    if action == 'select':
        research.is_selected = True
        research.is_excluded = False
    elif action == 'exclude':
        research.is_selected = False
        research.is_excluded = True
    else:  # toggle
        if research.is_selected:
            research.is_selected = False
        elif research.is_excluded:
            research.is_excluded = False
        else:
            research.is_selected = True
    
    research.save()
    
    # Return updated button state (for HTMX)
    if request.headers.get('HX-Request'):
        context = {'research': research}
        return render(request, 'research/partials/selection_buttons.html', context)
    
    # Fallback for non-HTMX
    return redirect('research:request_detail', pk=research.creation_request.pk)


@login_required
def request_list(request):
    """
    List all content creation requests for the user.
    """
    requests = ContentCreationRequest.objects.filter(user=request.user)
    
    context = {
        'requests': requests,
    }
    
    return render(request, 'research/request_list.html', context)


@login_required
@require_http_methods(["POST"])
def request_generate_content(request, pk):
    """
    Trigger evidence-grounded content generation from research request findings.
    """
    from content.services.generation_service import ContentGenerationService
    
    custom_instructions = request.POST.get('custom_instructions', '').strip()
    result = ContentGenerationService.generate_draft_for_request(
        creation_request_id=pk,
        user=request.user,
        custom_instructions=custom_instructions or None
    )
    
    if result['success']:
        messages.success(
            request,
            f"Draft generated successfully using {result['evidence_count']} research sources! AI Review Stage 1 executed."
        )
        return redirect('content:detail', pk=result['content'].pk)
    else:
        messages.error(request, result['error'])
        return redirect('research:request_detail', pk=pk)

