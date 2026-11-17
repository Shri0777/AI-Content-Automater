"""Run the local load test: python manage.py load_test --pipelines 100.

The work is done in core/loadtest.py; this file only runs it and prints
what happened.
"""

import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core import loadtest

POLL_SECONDS = 5


class Command(BaseCommand):
    """Make a burst of due posts and measure how the stack copes."""

    help = "Make a burst of scheduled posts (demo mode only) and report timings."

    def add_arguments(self, parser):
        """Read --pipelines, --timeout and --keep."""
        parser.add_argument("--pipelines", type=int, default=100)
        parser.add_argument("--timeout", type=int, default=900)
        parser.add_argument("--keep", action="store_true")

    def handle(self, *args, **options):
        """Make the burst, wait for it, report, and clean up."""
        if not settings.DEMO_MODE:
            raise CommandError("The load test only runs in demo mode.")
        started = timezone.now()
        run_id, plans = loadtest.make_burst(options["pipelines"])
        total = len(plans) * loadtest.SLOTS_PER_PLAN
        self.stdout.write(f"Run {run_id}: {total} posts due now.")
        peak_connections = self.wait(plans, total, options["timeout"])
        self.report(plans, total, started, peak_connections)
        if not options["keep"]:
            removed = loadtest.delete_burst(run_id)
            self.stdout.write(f"Removed {removed} load-test users.")

    def wait(self, plans, total, timeout):
        """Poll until every post is finished or timeout seconds pass."""
        deadline = time.monotonic() + timeout
        peak_connections = 0
        while time.monotonic() < deadline:
            counts = loadtest.progress(plans)
            peak_connections = max(peak_connections, loadtest.database_connections())
            self.stdout.write(f"  {timezone.now():%H:%M:%S} {counts}")
            if loadtest.count_finished(counts) >= total:
                break
            time.sleep(POLL_SECONDS)
        return peak_connections

    def report(self, plans, total, started, peak_connections):
        """Print the measurements."""
        counts = loadtest.progress(plans)
        claim_lags, making_times = loadtest.timings(plans)
        elapsed = (timezone.now() - started).total_seconds()
        self.stdout.write("Results:")
        self.stdout.write(
            f"  posts finished: {loadtest.count_finished(counts)} of {total}"
        )
        self.stdout.write(f"  by status: {counts}")
        self.stdout.write(f"  whole burst done in: {elapsed:.0f} s")
        for name, values in [("claim lag", claim_lags), ("making time", making_times)]:
            self.stdout.write(
                f"  {name}: p50 {loadtest.percentile(values, 0.5):.1f} s, "
                f"p99 {loadtest.percentile(values, 0.99):.1f} s, "
                f"max {max(values, default=0):.1f} s"
            )
        self.stdout.write(f"  peak database connections: {peak_connections}")
