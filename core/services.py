"""Shared helper functions used by more than one app."""

from django.db import DatabaseError, connection


def is_database_reachable():
    """Return True if the database answers a tiny query."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return False
    return True
