"""Read-only presentation views for the shared application experience."""

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from ai_providers.models import ProviderConfig
from content.models import Content, ContentPublication
from content.services.buffer_service import BufferPublishingService
from research.models import ContentCreationRequest


@login_required
def dashboard(request):
    """Show the authenticated user's actual workflow state without side effects."""
    contents = Content.objects.filter(owner=request.user).select_related("current_version")
    publications = ContentPublication.objects.filter(user=request.user)
    text_provider = ProviderConfig.objects.filter(
        user=request.user, capability="text", is_active=True
    ).first()
    buffer_status = BufferPublishingService().get_connection_status()

    context = {
        "content_total": contents.count(),
        "needs_review_count": contents.filter(lifecycle_state="pending_review").count(),
        "approved_count": contents.filter(
            lifecycle_state__in=["approved", "ready_to_publish"]
        ).count(),
        "scheduled_count": publications.filter(status="scheduled").count(),
        "recent_content": contents.order_by("-updated_at")[:6],
        "recent_requests": ContentCreationRequest.objects.filter(user=request.user).order_by(
            "-updated_at"
        )[:5],
        "publication_summary": publications.values("status").annotate(total=Count("id")),
        "text_provider": text_provider,
        "buffer_configured": buffer_status.get("configured", False),
        "buffer_connected": buffer_status.get("connected", False),
    }
    return render(request, "frontend/dashboard.html", context)


@login_required
def publishing_overview(request):
    """Provide an accurate read-only publication history and reconciliation queue."""
    publications = (
        ContentPublication.objects.filter(user=request.user)
        .select_related("content", "content_version")
        .order_by("-created_at")
    )
    return render(
        request,
        "frontend/pages/publishing.html",
        {
            "publications": publications,
            "ambiguous_count": publications.filter(status="ambiguous").count(),
            "scheduled_count": publications.filter(status="scheduled").count(),
            "buffer_status": BufferPublishingService().get_connection_status(),
        },
    )


@login_required
def help_page(request):
    """Describe only the currently implemented workflow and safety boundaries."""
    return render(request, "frontend/pages/help.html")
