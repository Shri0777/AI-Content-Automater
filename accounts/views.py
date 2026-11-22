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
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from accounts import services
from accounts.serializers import (
    ConfirmPasswordSerializer,
    LoginResultSerializer,
    LoginSerializer,
    MeUpdateSerializer,
    RecoverResultSerializer,
    RecoverSerializer,
    RecoveryCodesSerializer,
    RegisterResultSerializer,
    RegisterSerializer,
    SummarySerializer,
    UserSerializer,
)
from core.errors import AppError
from notifications.services import count_unread
from social.services import count_accounts_needing_attention
from studio.services import count_awaiting_approval


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

    @extend_schema(
        request=RegisterSerializer, responses={201: RegisterResultSerializer}
    )
    def post(self, request):
        """Create the user; return their details and recovery codes (shown once)."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.register_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            invite_code=serializer.validated_data.get("invite_code"),
        )
        body = dict(UserSerializer(result["user"]).data)
        body["recovery_codes"] = result["recovery_codes"]
        return Response(body, status=201)


class RecoverView(PublicAuthView):
    """Reset a forgotten password with a recovery code."""

    @extend_schema(request=RecoverSerializer, responses=RecoverResultSerializer)
    def post(self, request):
        """Use one recovery code to set a new password."""
        serializer = RecoverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        codes_left = services.recover_account(
            email=serializer.validated_data["email"],
            typed_code=serializer.validated_data["recovery_code"],
            new_password=serializer.validated_data["new_password"],
        )
        detail = "Password changed. Log in with your new password."
        return Response({"detail": detail, "recovery_codes_left": codes_left})


class NewRecoveryCodesView(APIView):
    """Make a fresh set of recovery codes. The old ones stop working.

    The current password is asked for again: new codes can reset the
    password, so a stolen login token alone must not be enough to get them.
    """

    throttle_classes = [UserRateThrottle, ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(
        request=ConfirmPasswordSerializer, responses={201: RecoveryCodesSerializer}
    )
    def post(self, request):
        """Check the password, then replace the codes and show the new ones once."""
        serializer = ConfirmPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        codes = services.new_recovery_codes(
            request.user, serializer.validated_data["password"]
        )
        return Response({"recovery_codes": codes}, status=201)


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

    throttle_scope = "auth_refresh"

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


class MeSummaryView(APIView):
    """A small overview for badges, cheap enough to poll often."""

    @extend_schema(responses=SummarySerializer)
    def get(self, request):
        """Return the counts the frontend shows as badges."""
        user = request.user
        summary = {
            "unread_notifications": count_unread(user),
            "posts_awaiting_approval": count_awaiting_approval(user),
            "accounts_needing_attention": count_accounts_needing_attention(user),
        }
        return Response(summary)
