import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q

from content.models import Content, ContentVersion
from content.forms import ContentForm, ContentVersionForm
from content.authorization import user_owns_content

logger = logging.getLogger(__name__)


@login_required
def content_list(request):
    """
    List all content owned by the current user.
    """
    contents = Content.objects.filter(owner=request.user)
    query = request.GET.get("q", "").strip()
    selected_state = request.GET.get("state", "").strip()
    sort = request.GET.get("sort", "updated")
    valid_states = {value for value, _label in Content.LIFECYCLE_CHOICES}
    valid_sorts = {"updated": "-updated_at", "created": "-created_at"}

    if query:
        contents = contents.filter(Q(title__icontains=query) | Q(topic__icontains=query))
    if selected_state in valid_states:
        contents = contents.filter(lifecycle_state=selected_state)

    contents = contents.order_by(valid_sorts.get(sort, valid_sorts["updated"]))
    page_obj = Paginator(contents, 12).get_page(request.GET.get("page"))
    # Support .count() call on contents for compatibility with QuerySet tests
    page_obj.count = lambda *args, **kwargs: page_obj.paginator.count
    return render(request, 'content/list.html', {
        'contents': page_obj,
        'page_obj': page_obj,
        'query': query,
        'selected_state': selected_state,
        'sort': sort if sort in valid_sorts else 'updated',
        'lifecycle_choices': Content.LIFECYCLE_CHOICES,
    })


@login_required
@require_http_methods(["GET", "POST"])
def content_create(request):
    """
    Create new content with initial version.
    """
    if request.method == 'POST':
        content_form = ContentForm(request.POST)
        version_form = ContentVersionForm(request.POST)

        if content_form.is_valid() and version_form.is_valid():
            with transaction.atomic():
                # Create content
                content = content_form.save(commit=False)
                content.owner = request.user
                content.save()

                # Create initial version
                version = version_form.save(commit=False)
                version.content = content
                version.version_number = 1
                version.created_by = request.user
                version.save()

                # Set current version
                content.current_version = version
                content.save(update_fields=['current_version'])

                messages.success(request, f'Content "{content.title}" created successfully.')
                return redirect('content:detail', pk=content.pk)
    else:
        content_form = ContentForm()
        version_form = ContentVersionForm()

    return render(request, 'content/create.html', {
        'content_form': content_form,
        'version_form': version_form
    })


@login_required
@user_owns_content
def content_detail(request, pk):
    """
    Display content details, version history, research evidence provenance,
    and quality review results.
    """
    content = get_object_or_404(Content, pk=pk)
    current_version = content.current_version
    status_info = content.get_status_info()

    # Evidence associations (Phase 4 traceability)
    evidence_associations = (
        content.research_associations
        .select_related('research')
        .order_by('citation_index', '-associated_at')
    )

    # Reviews for current version
    reviews = current_version.reviews.order_by('stage', '-created_at') if current_version else []
    latest_review = reviews.first() if reviews else None

    # Bounded revision limit tracking (FR-010: max 2 automated corrections)
    ai_revisions_count = content.versions.filter(
        change_summary__icontains='Automated revision'
    ).count()
    can_auto_correct = ai_revisions_count < 2 and current_version is not None

    # Phase 5: Observable workflow summary and pipeline state
    from content.services.workflow_orchestrator import WorkflowOrchestratorService
    workflow_summary = WorkflowOrchestratorService.get_workflow_summary(content)

    # Phase 6: Buffer Social Publishing & Scheduling
    from content.services.buffer_service import BufferPublishingService
    buffer_service = BufferPublishingService()
    buffer_status = buffer_service.get_connection_status()
    buffer_profiles = []
    if buffer_status.get('connected'):
        try:
            buffer_profiles = buffer_service.get_profiles()
        except Exception:
            logger.warning('Buffer destinations unavailable for content detail; hiding unverified channels.')
            buffer_status = {**buffer_status, 'connected': False, 'status': 'error',
                             'error': 'Could not verify Buffer destinations. Publishing is disabled until the connection is healthy.'}
    publications = content.publications.select_related('content_version').order_by('-created_at')[:10]
    can_publish = (
        current_version is not None
        and current_version.is_approved
        and content.lifecycle_state in ['approved', 'ready_to_publish']
    )

    # Get associated media records
    from content.models import Media
    media_records = Media.objects.filter(content=content).order_by('-created_at')

    return render(request, 'content/detail.html', {
        'content': content,
        'current_version': current_version,
        'status_info': status_info,
        'evidence_associations': evidence_associations,
        'reviews': reviews,
        'latest_review': latest_review,
        'ai_revisions_count': ai_revisions_count,
        'can_auto_correct': can_auto_correct,
        'workflow_summary': workflow_summary,
        'pipeline_stages': workflow_summary['pipeline_stages'],
        'active_prep': workflow_summary['active_prep'],
        'preparations': workflow_summary['preparations'],
        'can_prepare': workflow_summary['can_prepare'],
        'recent_audit_logs': workflow_summary['recent_audit_logs'],
        'buffer_status': buffer_status,
        'buffer_profiles': buffer_profiles,
        'publications': publications,
        'can_publish': can_publish,
        'media_records': media_records,
    })


@login_required
@user_owns_content
@require_http_methods(["GET", "POST"])
def content_edit(request, pk):
    """
    Edit content metadata and optionally create new version.
    A material edit invalidates previous approvals and resets to in_progress.
    """
    content = get_object_or_404(Content, pk=pk)

    if request.method == 'POST':
        content_form = ContentForm(request.POST, instance=content)
        version_form = ContentVersionForm(request.POST)

        create_version = request.POST.get('create_version') == 'true'

        if content_form.is_valid():
            with transaction.atomic():
                # Update content metadata
                content = content_form.save()

                # Create new version if requested and form is valid
                if create_version and version_form.is_valid():
                    new_version = ContentVersion.create_next_version(
                        content=content,
                        created_by=request.user,
                        content_text=version_form.cleaned_data['content_text'],
                        change_summary=version_form.cleaned_data.get('change_summary', '')
                    )

                    # Update current version
                    content.current_version = new_version

                    # Material edit invalidates approved status and preparations
                    if content.lifecycle_state in ('approved', 'ready_to_publish'):
                        content.lifecycle_state = 'in_progress'

                    content.save(update_fields=['current_version', 'lifecycle_state', 'updated_at'])

                    from content.services.publishing_service import PublishingPreparationService
                    from content.models import WorkflowAuditLog
                    PublishingPreparationService.invalidate_preparations_for_content(
                        content=content,
                        reason=f"Material edit: new version v{new_version.version_number} created.",
                        user=request.user
                    )
                    WorkflowAuditLog.objects.create(
                        content=content,
                        content_version=new_version,
                        user=request.user,
                        event_type='material_edit',
                        from_state='approved',
                        to_state=content.lifecycle_state,
                        message=f"Manual material edit created version v{new_version.version_number}. Previous approvals and preparations invalidated.",
                        details={'version_number': new_version.version_number}
                    )

                    messages.success(request, 'Content updated with new version. Previous approvals invalidated.')
                else:
                    messages.success(request, 'Content metadata updated.')

                return redirect('content:detail', pk=content.pk)
    else:
        content_form = ContentForm(instance=content)
        version_form = ContentVersionForm(
            initial={
                'content_text': content.current_version.content_text if content.current_version else ''
            }
        )

    return render(request, 'content/edit.html', {
        'content': content,
        'content_form': content_form,
        'version_form': version_form
    })


@login_required
@user_owns_content
@require_http_methods(["POST"])
def content_trigger_review(request, pk):
    """
    Trigger an automated quality review on the current version.
    """
    from content.services.review_service import QualityReviewService

    content = get_object_or_404(Content, pk=pk)
    if not content.current_version:
        messages.error(request, 'No content version available to review.')
        return redirect('content:detail', pk=pk)

    existing_reviews = content.current_version.reviews.count()
    stage = 2 if existing_reviews > 0 else 1

    review = QualityReviewService.review_version(
        content_version=content.current_version,
        stage=stage,
        user=request.user
    )

    messages.success(
        request,
        f"Quality Review Stage {stage} completed: Status is {review.get_status_display()} (Score: {review.score:.2f})."
    )
    return redirect('content:detail', pk=pk)


@login_required
@user_owns_content
@require_http_methods(["POST"])
def content_apply_correction(request, pk):
    """
    Apply a bounded automated correction to the current version based on review findings.
    """
    from content.services.correction_service import ContentCorrectionService

    notes = request.POST.get('user_notes', '').strip()
    result = ContentCorrectionService.apply_bounded_correction(
        content_id=pk,
        user=request.user,
        user_notes=notes or None
    )

    if result['success']:
        messages.success(
            request,
            f"Automated revision applied! Version {result['version'].version_number} created and Stage 2 review completed (Score: {result['review'].score:.2f})."
        )
    else:
        messages.error(request, result['error'])

    return redirect('content:detail', pk=pk)


@login_required
@user_owns_content
@require_http_methods(["POST"])
def content_approve_version(request, pk):
    """
    Explicit human approval gate for a specific ContentVersion.
    """
    from content.services.workflow_orchestrator import WorkflowOrchestratorService

    version_number_raw = request.POST.get('version_number')
    version_number = int(version_number_raw) if version_number_raw and str(version_number_raw).isdigit() else None

    result = WorkflowOrchestratorService.approve_content_version(
        content_id=pk,
        user=request.user,
        version_number=version_number
    )

    if result['success']:
        if result.get('already_approved'):
            messages.info(request, result['message'])
        else:
            messages.success(request, result['message'])
    else:
        messages.error(request, result['error'])

    return redirect('content:detail', pk=pk)


@login_required
@user_owns_content
@require_http_methods(["POST"])
def content_prepare_publishing(request, pk):
    """
    Final validation gate and publishing preparation for target platforms (Phase 5).
    """
    from content.services.workflow_orchestrator import WorkflowOrchestratorService

    platforms = request.POST.getlist('platforms')
    if not platforms:
        platforms = ['twitter', 'linkedin']

    result = WorkflowOrchestratorService.prepare_content_for_publishing(
        content_id=pk,
        user=request.user,
        target_platforms=platforms
    )

    if result['success']:
        messages.success(
            request,
            f"Content prepared successfully for publication ({', '.join(platforms)})! State advanced to Ready to Publish."
        )
    else:
        messages.error(request, result['error'])

    return redirect('content:detail', pk=pk)



@login_required
@user_owns_content
@require_http_methods(["POST"])
def content_delete(request, pk):
    """
    Delete content (soft delete or hard delete).
    """
    content = get_object_or_404(Content, pk=pk)
    title = content.title

    content.delete()

    messages.success(request, f'Content "{title}" deleted successfully.')
    return redirect('content:list')


@login_required
@user_owns_content
def content_versions(request, pk):
    """
    List all versions of a content item.
    """
    content = get_object_or_404(Content, pk=pk)
    versions = content.versions.all()

    return render(request, 'content/versions.html', {
        'content': content,
        'versions': versions
    })


@login_required
@user_owns_content
def content_transition(request, pk):
    """
    Transition content to a new lifecycle state. Supports both form redirect and JSON API callers.
    """
    if request.method == 'POST':
        content = get_object_or_404(Content, pk=pk)
        new_state = request.POST.get('new_state')

        # Also support JSON request body
        if not new_state and request.content_type == 'application/json':
            try:
                import json
                data = json.loads(request.body)
                new_state = data.get('target_state') or data.get('new_state')
            except (ValueError, TypeError):
                pass

        # Gracefully handle clients/forms that submit the transition endpoint
        # without a button value. Infer only when the state machine has one
        # unambiguous next state; never guess when multiple transitions exist.
        if not new_state:
            available_transitions = content._get_available_transitions()
            if len(available_transitions) == 1:
                new_state = available_transitions[0]

        if not new_state:
            error = 'Choose a valid workflow action before submitting.'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                from django.http import JsonResponse
                return JsonResponse({'success': False, 'error': error}, status=400)
            messages.error(request, error)
            return redirect('content:detail', pk=content.pk)

        from content.services.workflow_orchestrator import WorkflowOrchestratorService
        result = WorkflowOrchestratorService.execute_state_transition(
            content_id=pk,
            target_state=new_state,
            user=request.user,
            reason=request.POST.get('reason')
        )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            from django.http import JsonResponse
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'lifecycle_state': result['lifecycle_state'],
                    'content_id': pk
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error']
                }, status=400)

        if result['success']:
            messages.success(request, f"Content transitioned to {result['content'].get_lifecycle_state_display()}.")
        else:
            messages.error(request, f"Transition failed: {result['error']}")

        return redirect('content:detail', pk=content.pk)

    return redirect('content:detail', pk=pk)


@login_required
@user_owns_content
@require_http_methods(["POST"])
def content_publish(request, pk):
    """
    Publish or schedule approved content via Buffer (Phase 6).
    """
    from content.services.publishing_orchestrator import BufferPublishingOrchestrator
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone
    from datetime import datetime

    profile_ids = request.POST.getlist('profile_ids')
    mode = request.POST.get('mode', 'immediate')
    scheduled_at_raw = request.POST.get('scheduled_at')
    idempotency_key = request.POST.get('idempotency_key') or None

    scheduled_at = None
    if mode == 'scheduled' and scheduled_at_raw:
        try:
            scheduled_at = parse_datetime(scheduled_at_raw)
            if not scheduled_at:
                scheduled_at = datetime.fromisoformat(scheduled_at_raw)
            if scheduled_at and timezone.is_naive(scheduled_at):
                scheduled_at = timezone.make_aware(scheduled_at)
        except Exception:
            messages.error(request, f"Invalid scheduled date/time format: {scheduled_at_raw}")
            return redirect('content:detail', pk=pk)

    result = BufferPublishingOrchestrator.execute_publishing(
        content_id=pk,
        user=request.user,
        profile_ids=profile_ids,
        mode=mode,
        scheduled_at=scheduled_at,
        client_idempotency_key=idempotency_key
    )

    if result.get('partial_success'):
        failed_errs = [r.get('error') for r in result.get('results', []) if not r.get('success')]
        err = "; ".join(filter(None, failed_errs)) or "Some channels failed."
        messages.warning(
            request,
            f"Partial success: {result['successful_count']}/{result['total_targets']} destinations succeeded. Issues: {err}"
        )
    elif result['success']:
        if mode == 'scheduled':
            messages.success(request, f"Successfully scheduled post across {result['successful_count']} destination(s)!")
        else:
            messages.success(request, f"Successfully published post across {result['successful_count']} destination(s)!")
    else:
        err = result.get('error')
        if not err and result.get('results'):
            failed_errs = [r.get('error') for r in result['results'] if not r.get('success')]
            err = "; ".join(filter(None, failed_errs)) or "Publishing failed for one or more profiles."
        messages.error(request, f"Publishing failed: {err}")

    return redirect('content:detail', pk=pk)


@login_required
@user_owns_content
@require_http_methods(["POST"])
def content_reconcile_publication(request, pk, pub_id):
    """
    Manually reconcile an ambiguous publication attempt (Phase 6).
    """
    from content.services.publishing_orchestrator import BufferPublishingOrchestrator

    resolution = request.POST.get('resolution')
    external_post_id = request.POST.get('external_post_id') or None

    result = BufferPublishingOrchestrator.reconcile_publication(
        publication_id=pub_id,
        user=request.user,
        resolution=resolution,
        external_post_id=external_post_id
    )

    if result['success']:
        messages.success(request, f"Publication #{pub_id} was successfully marked as {result['publication'].status}.")
    else:
        messages.error(request, f"Reconciliation failed: {result.get('error')}")

    return redirect('content:detail', pk=pk)
