"""API endpoints for registering, logging in and out, and the user's own page.

The access token is sent in the response body. The refresh token is kept in
an httpOnly cookie that browser scripts cannot read (see ADR-009). Requests
that use that cookie must also send the X-Requested-By header, which a form
on another website cannot add.
"""

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts import services
from accounts.serializers import (
    LoginResultSerializer,
    LoginSerializer,
    MeUpdateSerializer,
    RegisterSerializer,
    UserSerializer,
)
from core.errors import AppError


class MissingRequiredHeader(AppError):
    """Raised when a cookie-based request lacks the X-Requested-By header."""

    status = 403
    code = "missing_required_header"
    title = "Missing header"


def require_auth_header(request):
    """Stop the request unless it carries the X-Requested-By header."""
    header_name = settings.REQUIRED_AUTH_HEADER
    if not request.headers.get(header_name):
        raise MissingRequiredHeader(f"This request must send the {header_name} header.")


def set_refresh_cookie(response, refresh_token):
    """Put the refresh token in a cookie that browser scripts cannot read."""
    lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
    )


class PublicAuthView(APIView):
    """Shared settings for auth endpoints: no login needed, 10 tries a minute."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class RegisterView(PublicAuthView):
    """Create a new account (needs an invite code in invite mode)."""

    @extend_schema(request=RegisterSerializer, responses={201: UserSerializer})
    def post(self, request):
        """Check the details, create the user and return their public details."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.register_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            invite_code=serializer.validated_data.get("invite_code"),
        )
        return Response(UserSerializer(user).data, status=201)


class LoginView(PublicAuthView):
    """Log in with email and password."""

    @extend_schema(request=LoginSerializer, responses=LoginResultSerializer)
    def post(self, request):
        """Return an access token and set the refresh cookie."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.log_in(
            request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        body = {"access": result["access"], "user": UserSerializer(result["user"]).data}
        response = Response(body)
        set_refresh_cookie(response, result["refresh"])
        return response


class RefreshView(PublicAuthView):
    """Get a new access token using the refresh cookie."""

    @extend_schema(request=None, responses=LoginResultSerializer)
    def post(self, request):
        """Return a new access token and replace the refresh cookie."""
        require_auth_header(request)
        refresh_token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not refresh_token:
            raise services.NotLoggedIn("You are not logged in.")
        tokens = services.refresh_login(refresh_token)
        response = Response({"access": tokens["access"]})
        set_refresh_cookie(response, tokens["refresh"])
        return response


class LogoutView(PublicAuthView):
    """Log out: cancel the refresh token and remove the cookie."""

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        """Cancel the refresh token (if any) and delete the cookie."""
        require_auth_header(request)
        refresh_token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if refresh_token:
            services.log_out(refresh_token)
        response = Response(status=204)
        response.delete_cookie(
            settings.REFRESH_COOKIE_NAME,
            path=settings.REFRESH_COOKIE_PATH,
            samesite=settings.REFRESH_COOKIE_SAMESITE,
        )
        return response


class MeView(APIView):
    """The logged-in user's own details."""

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        """Show the logged-in user's details."""
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=MeUpdateSerializer, responses=UserSerializer)
    def patch(self, request):
        """Change the details users may change (currently their timezone)."""
        serializer = MeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)
