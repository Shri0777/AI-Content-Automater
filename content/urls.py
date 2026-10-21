from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
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
]
