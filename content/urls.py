from django.urls import path
from . import views
from .views import campaign_views, notification_views, media_views, analytics_views

app_name = 'content'

urlpatterns = [
    # Content management
    path('', views.content_list, name='list'),
    path('create/', views.content_create, name='create'),
    path('<int:pk>/', views.content_detail, name='detail'),
    path('<int:pk>/edit/', views.content_edit, name='edit'),
    path('<int:pk>/delete/', views.content_delete, name='delete'),
    path('<int:pk>/versions/', views.content_versions, name='versions'),
    path('<int:pk>/transition/', views.content_transition, name='transition'),
    path('<int:pk>/review/', views.content_trigger_review, name='trigger_review'),
    path('<int:pk>/correct/', views.content_apply_correction, name='apply_correction'),
    path('<int:pk>/approve/', views.content_approve_version, name='approve_version'),
    path('<int:pk>/prepare-publishing/', views.content_prepare_publishing, name='prepare_publishing'),
    path('<int:pk>/publish/', views.content_publish, name='publish'),
    path('<int:pk>/publications/<int:pub_id>/reconcile/', views.content_reconcile_publication, name='reconcile_publication'),

    # Campaigns
    path('campaigns/', campaign_views.campaign_list, name='campaign_list'),
    path('campaigns/create/', campaign_views.campaign_create, name='campaign_create'),
    path('campaigns/<int:pk>/', campaign_views.campaign_detail, name='campaign_detail'),
    path('campaigns/<int:pk>/activate/', campaign_views.campaign_activate, name='campaign_activate'),
    path('campaigns/<int:pk>/pause/', campaign_views.campaign_pause, name='campaign_pause'),
    path('campaigns/<int:pk>/execute/', campaign_views.campaign_execute_now, name='campaign_execute'),
    path('campaigns/<int:pk>/delete/', campaign_views.campaign_delete, name='campaign_delete'),

    # Notifications
    path('notifications/', notification_views.notification_list, name='notification_list'),
    path('notifications/<int:pk>/mark-read/', notification_views.notification_mark_read, name='notification_mark_read'),
    path('notifications/mark-all-read/', notification_views.notification_mark_all_read, name='notification_mark_all_read'),
    path('notifications/preferences/', notification_views.notification_preferences, name='notification_preferences'),

    # Media
    path('media/', media_views.media_list, name='media_list'),
    path('media/upload/', media_views.media_upload, name='media_upload'),
    path('media/<int:pk>/', media_views.media_detail, name='media_detail'),
    path('media/<int:pk>/delete/', media_views.media_delete, name='media_delete'),

    # Analytics
    path('analytics/', analytics_views.analytics_dashboard, name='analytics_dashboard'),
    path('analytics/publishing/', analytics_views.analytics_publishing, name='analytics_publishing'),
    path('analytics/campaigns/', analytics_views.analytics_campaigns, name='analytics_campaigns'),
]
