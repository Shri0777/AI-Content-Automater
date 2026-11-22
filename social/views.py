"""API endpoints for linking and unlinking social accounts."""

from django.http import HttpResponseRedirect
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from social import oauth, platform_apps, services
from social.models import PLATFORM_CHOICES
from social.platforms import get_publisher, is_ready_to_link
from social.serializers import (
    BufferChannelSerializer,
    BufferKeySerializer,
    BufferLinkSerializer,
    LinkStartSerializer,
    PlatformAppInputSerializer,
    PlatformAppSerializer,
    PlatformSerializer,
    SocialAccountSerializer,
)


class SocialAccountListView(APIView):
    """List the user's linked accounts."""

    @extend_schema(responses=SocialAccountSerializer(many=True))
    def get(self, request):
        """Return every account the user has linked."""
        accounts = services.get_accounts(request.user)
        return Response(SocialAccountSerializer(accounts, many=True).data)


class SocialAccountDetailView(APIView):
    """Unlink one account."""

    @extend_schema(responses={204: None})
    def delete(self, request, account_id):
        """Cancel the account's tokens and remove it, if it is the user's."""
        services.unlink_account(request.user, account_id)
        return Response(status=204)


def link_method_of(platform):
    """Return how accounts on platform are linked: oauth, api_key or demo."""
    if platform == "demo":
        return "demo"
    if get_publisher(platform).uses_oauth:
        return "oauth"
    return "api_key"


def describe_platform(user, platform, name):
    """Return what the platform list shows about one platform for the user."""
    takes_app = platform in platform_apps.APP_PLATFORMS
    return {
        "platform": platform,
        "name": name,
        "link_method": link_method_of(platform),
        "ready": is_ready_to_link(platform, user),
        "app_saved": takes_app and platform_apps.has_saved_app(user, platform),
        "callback_url": oauth.callback_url(platform) if takes_app else None,
    }


class PlatformListView(APIView):
    """Which platforms exist and which the user can link right now."""

    @extend_schema(responses=PlatformSerializer(many=True))
    def get(self, request):
        """Return every platform with how it is linked and if it is ready."""
        platforms = []
        for platform, name in PLATFORM_CHOICES:
            platforms.append(describe_platform(request.user, platform, name))
        return Response(PlatformSerializer(platforms, many=True).data)


class PlatformAppListView(APIView):
    """The developer apps the user saved for X, LinkedIn and Facebook."""

    @extend_schema(responses=PlatformAppSerializer(many=True))
    def get(self, request):
        """Return the user's saved apps (ids only, never secrets)."""
        apps = platform_apps.list_apps(request.user)
        return Response(PlatformAppSerializer(apps, many=True).data)


class PlatformAppDetailView(APIView):
    """Save or remove the user's developer app for one platform."""

    @extend_schema(request=PlatformAppInputSerializer, responses=PlatformAppSerializer)
    def put(self, request, platform):
        """Save the app's id and secret (the secret is stored encrypted)."""
        platform_apps.check_takes_an_app(platform)
        serializer = PlatformAppInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        app = platform_apps.save_app(
            request.user,
            platform,
            serializer.validated_data["client_id"],
            serializer.validated_data["client_secret"],
        )
        return Response(PlatformAppSerializer(app).data)

    @extend_schema(responses={204: None})
    def delete(self, request, platform):
        """Remove the app. Accounts linked through it will need relinking."""
        platform_apps.delete_app(request.user, platform)
        return Response(status=204)


class LinkDemoAccountView(APIView):
    """Link an account on the fake demo network (demo mode only)."""

    @extend_schema(request=None, responses={201: SocialAccountSerializer})
    def post(self, request):
        """Create a demo account straight away; there is no login page."""
        account = services.link_demo_account(request.user)
        return Response(SocialAccountSerializer(account).data, status=201)


class LinkBufferView(APIView):
    """Link Buffer channels with a personal Buffer API key."""

    @extend_schema(
        request=BufferLinkSerializer,
        responses={201: SocialAccountSerializer(many=True)},
    )
    def post(self, request):
        """Find the key's channels and link them (or only the chosen ones)."""
        serializer = BufferLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        accounts = services.link_buffer_accounts(
            request.user,
            serializer.validated_data["api_key"],
            serializer.validated_data.get("channel_ids", []),
        )
        return Response(SocialAccountSerializer(accounts, many=True).data, status=201)


class BufferChannelsView(APIView):
    """List the channels a Buffer API key can see, without linking them."""

    @extend_schema(
        request=BufferKeySerializer, responses=BufferChannelSerializer(many=True)
    )
    def post(self, request):
        """Return each channel's id, name and network, for the user to choose."""
        serializer = BufferKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channels = services.list_buffer_channels(serializer.validated_data["api_key"])
        return Response(BufferChannelSerializer(channels, many=True).data)


class LinkStartView(APIView):
    """Start linking an X, LinkedIn or Facebook account."""

    @extend_schema(request=None, responses=LinkStartSerializer)
    def post(self, request, platform):
        """Return the platform page where the user approves the link."""
        url = oauth.start_link(request.user, platform)
        return Response({"authorization_url": url})


class LinkCallbackView(APIView):
    """Where the platform sends the user back after they approve (or cancel).

    The user arrives from the platform's website, without our login token,
    so this view needs no login: the single-use state identifies the attempt.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(responses={302: None})
    def get(self, request, platform):
        """Finish linking and send the user on to the frontend's result page."""
        return HttpResponseRedirect(oauth.handle_callback(platform, request.GET))
