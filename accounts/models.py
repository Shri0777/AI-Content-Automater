"""Database tables for people who use the app.

Users log in with their email address instead of a username. Each user has
a tier (everyone starts on "free") and a timezone, which is used to decide
when "today" starts for daily limits and schedules.
"""

import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Creates users and admin users that are identified by email."""

    def create_user(self, email, password):
        """Create and save a normal user."""
        if not email:
            raise ValueError("Every user needs an email address.")
        user = self.model(email=self.normalize_email(email))
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password):
        """Create and save a user who can use the admin site."""
        user = self.create_user(email=email, password=password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        return user


class User(AbstractUser):
    """A person who uses the app. They log in with their email address."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    timezone = models.CharField(max_length=64, default="UTC")
    tier = models.CharField(max_length=32, default="free")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
