"""What account data goes into and comes out of the API."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    """The details of a user that the API shows. Never includes the password."""

    class Meta:
        model = User
        fields = ["id", "email", "timezone", "tier", "date_joined"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    """The fields needed to create an account."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    invite_code = serializers.CharField(
        required=False, allow_blank=True, write_only=True
    )

    def validate_email(self, value):
        """Refuse an email address that already has an account."""
        email = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return email

    def validate(self, data):
        """Check the password with Django's password rules."""
        new_user = User(email=data["email"])
        try:
            validate_password(data["password"], user=new_user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from None
        return data


class RegisterResultSerializer(UserSerializer):
    """What registration sends back: the new user plus recovery codes."""

    recovery_codes = serializers.ListField(child=serializers.CharField())

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["recovery_codes"]
        read_only_fields = fields


class RecoverSerializer(serializers.Serializer):
    """The fields needed to reset a forgotten password with a recovery code."""

    email = serializers.EmailField()
    recovery_code = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        """Check the new password with Django's password rules."""
        account = User(email=data["email"])
        try:
            validate_password(data["new_password"], user=account)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                {"new_password": error.messages}
            ) from None
        return data


class RecoverResultSerializer(serializers.Serializer):
    """What a successful recovery sends back."""

    detail = serializers.CharField()
    recovery_codes_left = serializers.IntegerField()


class RecoveryCodesSerializer(serializers.Serializer):
    """A new set of recovery codes, shown once."""

    recovery_codes = serializers.ListField(child=serializers.CharField())


class LoginSerializer(serializers.Serializer):
    """The fields needed to log in."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class LoginResultSerializer(serializers.Serializer):
    """What a successful login or refresh sends back."""

    access = serializers.CharField()
    user = UserSerializer(required=False)


class SummarySerializer(serializers.Serializer):
    """A small overview the frontend polls to show badges."""

    unread_notifications = serializers.IntegerField()
    posts_awaiting_approval = serializers.IntegerField()
    accounts_needing_attention = serializers.IntegerField()


class MeUpdateSerializer(serializers.ModelSerializer):
    """The details users may change about themselves."""

    class Meta:
        model = User
        fields = ["timezone"]

    def validate_timezone(self, value):
        """Accept only real timezone names such as "Asia/Kolkata"."""
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError(
                f"'{value}' is not a known timezone."
            ) from None
        return value
