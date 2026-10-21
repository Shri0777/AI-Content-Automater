"""
URL configuration for research app.
"""
from django.urls import path
from . import views

app_name = 'research'

urlpatterns = [
    # Profile management
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    
    # Content creation requests
    path('request/new/', views.request_new, name='request_new'),
    path('request/<int:pk>/', views.request_detail, name='request_detail'),
    path('request/<int:pk>/execute/', views.request_execute, name='request_execute'),
    path('request/<int:pk>/generate/', views.request_generate_content, name='request_generate_content'),
    path('requests/', views.request_list, name='request_list'),
    
    # Research item actions
    path('research/<int:pk>/select/', views.research_select, name='research_select'),
]
