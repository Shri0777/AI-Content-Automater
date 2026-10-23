"""
Campaign management views (FR-029, FR-030, FR-031).
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone

from content.models import Campaign, CampaignExecution
from content.tasks.campaign_tasks import execute_campaign_task


@login_required
def campaign_list(request):
    """List all campaigns for the current user."""
    campaigns = Campaign.objects.filter(owner=request.user).order_by('-created_at')
    
    context = {
        'campaigns': campaigns,
        'page_title': 'My Campaigns'
    }
    return render(request, 'content/campaigns/list.html', context)


@login_required
def campaign_detail(request, pk):
    """Show campaign details and execution history."""
    campaign = get_object_or_404(Campaign, id=pk, owner=request.user)
    executions = CampaignExecution.objects.filter(
        campaign=campaign
    ).order_by('-created_at')[:20]
    
    context = {
        'campaign': campaign,
        'executions': executions,
        'page_title': f'Campaign: {campaign.name}'
    }
    return render(request, 'content/campaigns/detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def campaign_create(request):
    """Create a new campaign."""
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            topic = request.POST.get('topic', '').strip()
            frequency = request.POST.get('frequency', 'weekly')
            generation_instructions = request.POST.get('generation_instructions', '').strip()
            research_instructions = request.POST.get('research_instructions', '').strip()
            start_date_str = request.POST.get('start_date', '').strip()
            
            if not name or not topic:
                messages.error(request, 'Name and topic are required.')
                return render(request, 'content/campaigns/create.html')
            
            # Parse start_date if provided, otherwise use today
            from datetime import date
            if start_date_str:
                try:
                    start_date = date.fromisoformat(start_date_str)
                except ValueError:
                    start_date = timezone.now().date()
            else:
                start_date = timezone.now().date()
            
            campaign = Campaign.objects.create(
                owner=request.user,
                name=name,
                topic=topic,
                frequency=frequency,
                generation_instructions=generation_instructions,
                research_instructions=research_instructions,
                start_date=start_date,
                status='draft'
            )
            
            messages.success(request, f'Campaign "{campaign.name}" created successfully.')
            return redirect('content:campaign_detail', pk=campaign.id)
            
        except Exception as e:
            messages.error(request, f'Error creating campaign: {str(e)}')
    
    context = {
        'page_title': 'Create Campaign',
        'frequency_choices': Campaign.FREQUENCY_CHOICES
    }
    return render(request, 'content/campaigns/create.html', context)


@login_required
@require_http_methods(["POST"])
def campaign_activate(request, pk):
    """Activate a campaign and schedule first execution."""
    campaign = get_object_or_404(Campaign, id=pk, owner=request.user)
    
    if campaign.status != 'draft':
        messages.warning(request, 'Campaign is already active or completed.')
        return redirect('content:campaign_detail', pk=campaign.id)
    
    try:
        with transaction.atomic():
            campaign.status = 'active'
            campaign.start_date = timezone.now().date()
            campaign.next_execution = timezone.now()
            campaign.save()
        
        messages.success(request, f'Campaign "{campaign.name}" activated.')
    except Exception as e:
        messages.error(request, f'Error activating campaign: {str(e)}')
    
    return redirect('content:campaign_detail', pk=campaign.id)


@login_required
@require_http_methods(["POST"])
def campaign_pause(request, pk):
    """Pause an active campaign."""
    campaign = get_object_or_404(Campaign, id=pk, owner=request.user)
    
    if campaign.status != 'active':
        messages.warning(request, 'Campaign is not active.')
        return redirect('content:campaign_detail', pk=campaign.id)
    
    try:
        campaign.status = 'paused'
        campaign.save()
        messages.success(request, f'Campaign "{campaign.name}" paused.')
    except Exception as e:
        messages.error(request, f'Error pausing campaign: {str(e)}')
    
    return redirect('content:campaign_detail', pk=campaign.id)


@login_required
@require_http_methods(["POST"])
def campaign_execute_now(request, pk):
    """Manually trigger campaign execution."""
    campaign = get_object_or_404(Campaign, id=pk, owner=request.user)
    
    if campaign.status not in ['active', 'draft']:
        messages.warning(request, 'Campaign cannot be executed in current status.')
        return redirect('content:campaign_detail', pk=campaign.id)
    
    try:
        # Queue the task
        execute_campaign_task.delay(campaign.id)
        messages.success(request, f'Campaign "{campaign.name}" execution queued.')
    except Exception as e:
        messages.error(request, f'Error queueing execution: {str(e)}')
    
    return redirect('content:campaign_detail', pk=campaign.id)


@login_required
@require_http_methods(["POST"])
def campaign_delete(request, pk):
    """Delete a campaign."""
    campaign = get_object_or_404(Campaign, id=pk, owner=request.user)
    
    try:
        campaign_name = campaign.name
        campaign.delete()
        messages.success(request, f'Campaign "{campaign_name}" deleted.')
        return redirect('content:campaign_list')
    except Exception as e:
        messages.error(request, f'Error deleting campaign: {str(e)}')
        return redirect('content:campaign_detail', pk=campaign.id)
