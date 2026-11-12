"""Command for the operator to create invite codes.

Usage:  uv run python manage.py create_invite_codes 5
Each printed code lets one person create an account. Codes are shown only
once, because the database stores just their fingerprints.
"""

from django.core.management.base import BaseCommand

from accounts.services import create_invite_codes


class Command(BaseCommand):
    """Create single-use invite codes and print them."""

    help = "Create single-use invite codes and print them."

    def add_arguments(self, parser):
        """Read how many codes to create from the command line."""
        parser.add_argument("count", type=int, help="How many codes to create.")

    def handle(self, *args, **options):
        """Create the codes and print one per line."""
        codes = create_invite_codes(options["count"])
        self.stdout.write(f"Created {len(codes)} invite code(s). Each works once:")
        for code in codes:
            self.stdout.write(code)
