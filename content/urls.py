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
]
