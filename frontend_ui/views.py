from django.shortcuts import render

from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    """Render the main dashboard showing key metrics using real counts.
    """
    from content.models import ContentItem
    from research.models import ResearchRequest
    from ai_providers.models import ProviderConfig
    context = {
        'content_count': ContentItem.objects.count(),
        'research_count': ResearchRequest.objects.count(),
        'provider_count': ProviderConfig.objects.count(),
    }
    return render(request, 'frontend/dashboard.html', context)

