"""API endpoints for making posts and deciding what happens to them."""

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from studio import services
from studio.public_links import read_public_poster
from studio.serializers import PostDetailSerializer, PostSerializer


class PostPagination(CursorPagination):
    """Show posts 20 at a time, newest first."""

    page_size = 20
    ordering = "-created_at"


class GenerateNowView(APIView):
    """Make a post for a plan right now."""

    @extend_schema(request=None, responses={202: PostDetailSerializer})
    def post(self, request, plan_id):
        """Start making a post. Poll the post until it waits for approval."""
        post = services.start_generation(request.user, plan_id)
        return Response(PostDetailSerializer(post).data, status=202)


class PostListView(APIView):
    """The user's posts."""

    @extend_schema(
        parameters=[OpenApiParameter("status", OpenApiTypes.STR)],
        responses=PostSerializer(many=True),
    )
    def get(self, request):
        """Return one page of posts; add ?status=... to filter."""
        status = request.query_params.get("status", "")
        posts = services.get_posts(request.user, status)
        paginator = PostPagination()
        page = paginator.paginate_queryset(posts, request, view=self)
        return paginator.get_paginated_response(PostSerializer(page, many=True).data)


class PostDetailView(APIView):
    """One post with its versions, review, steps and publications."""

    @extend_schema(responses=PostDetailSerializer)
    def get(self, request, post_id):
        """Return everything about one post."""
        post = services.get_post(request.user, post_id)
        return Response(PostDetailSerializer(post).data)


class ApprovePostView(APIView):
    """Approve a post that is waiting, which publishes it."""

    @extend_schema(request=None, responses=PostDetailSerializer)
    def post(self, request, post_id):
        """Approve the post and start publishing it."""
        post = services.approve_post(request.user, post_id)
        return Response(PostDetailSerializer(post).data)


class RejectPostView(APIView):
    """Reject a post that is waiting, so it is never published."""

    @extend_schema(request=None, responses=PostDetailSerializer)
    def post(self, request, post_id):
        """Reject the post."""
        post = services.reject_post(request.user, post_id)
        return Response(PostDetailSerializer(post).data)


class PosterView(APIView):
    """The poster image of a post."""

    @extend_schema(responses={(200, "image/png"): OpenApiTypes.BINARY})
    def get(self, request, post_id):
        """Return the newest poster as a PNG image."""
        png_bytes = services.get_poster_bytes(request.user, post_id)
        return HttpResponse(png_bytes, content_type="image/png")


class PublicPosterView(APIView):
    """A poster image behind a signed link, for services such as Buffer.

    No login is needed: the signature in the address is the permission.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={(200, "image/png"): OpenApiTypes.BINARY})
    def get(self, request, token):
        """Return the poster as a PNG image if the link is valid."""
        return HttpResponse(read_public_poster(token), content_type="image/png")
