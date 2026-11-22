"""Web addresses for posts: /api/v1/posts/... and generate-now on a plan."""

from django.urls import path

from studio.views import (
    ApprovePostView,
    GenerateNowView,
    PostDetailView,
    PosterView,
    PostListView,
    PublicPosterView,
    RejectPostView,
    SlideView,
)

urlpatterns = [
    path(
        "plans/<uuid:plan_id>/generate-now/",
        GenerateNowView.as_view(),
        name="plan-generate-now",
    ),
    path("posts/", PostListView.as_view(), name="posts"),
    path("posts/<uuid:post_id>/", PostDetailView.as_view(), name="post-detail"),
    path(
        "posts/<uuid:post_id>/approve/",
        ApprovePostView.as_view(),
        name="post-approve",
    ),
    path(
        "posts/<uuid:post_id>/reject/",
        RejectPostView.as_view(),
        name="post-reject",
    ),
    path("posts/<uuid:post_id>/poster/", PosterView.as_view(), name="post-poster"),
    path(
        "posts/<uuid:post_id>/slides/<int:number>/",
        SlideView.as_view(),
        name="post-slide",
    ),
    path(
        "public/posters/<str:token>.png",
        PublicPosterView.as_view(),
        name="public-poster",
    ),
]
