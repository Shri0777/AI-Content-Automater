"""
Notification management views (FR-038).
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from content.models import Notification, NotificationPreference
from content.services.notification_service import NotificationService


@login_required
def notification_list(request):
    """List all notifications for the current user."""
    unread_only = request.GET.get('unread') == 'true'
    
    notifications = NotificationService.get_user_notifications(
        user=request.user,
        unread_only=unread_only,
        limit=50
    )
    
    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'showing_unread_only': unread_only,
        'page_title': 'Notifications'
    }
    return render(request, 'content/notifications/list.html', context)


@login_required
@require_http_methods(["POST"])
def notification_mark_read(request, pk):
    """Mark a notification as read."""
    result = NotificationService.mark_as_read(
        notification_id=pk,
        user=request.user
    )
    
    if result['success']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, 'Notification marked as read.')
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': result['error']})
        messages.error(request, result['error'])
    
    return redirect('content:notification_list')


@login_required
@require_http_methods(["POST"])
def notification_mark_all_read(request):
    """Mark all notifications as read."""
    try:
        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'count': count})
        
        messages.success(request, f'Marked {count} notification(s) as read.')
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)})
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('content:notification_list')


@login_required
def notification_preferences(request):
    """View and update notification preferences."""
    prefs, created = NotificationPreference.objects.get_or_create(
        user=request.user
    )
    
    if request.method == 'POST':
        try:
            prefs.email_enabled = request.POST.get('email_enabled') == 'on'
            prefs.in_app_enabled = request.POST.get('in_app_enabled') == 'on'
            prefs.save()
            
            messages.success(request, 'Notification preferences updated.')
            return redirect('content:notification_preferences')
        except Exception as e:
            messages.error(request, f'Error updating preferences: {str(e)}')
    
    context = {
        'preferences': prefs,
        'page_title': 'Notification Preferences'
    }
    return render(request, 'content/notifications/preferences.html', context)
