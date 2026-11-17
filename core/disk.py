"""Watch the disk that holds posters, so a full disk fails safely.

At DISK_WARN the cleanup job logs a warning. At DISK_STOP no new posts are
started and no news is read until space is freed: slots that wait too long
are skipped with a notification, which is better than crashing halfway.
"""

import logging
import shutil
from pathlib import Path

from django.conf import settings

DISK_WARN = 0.80
DISK_STOP = 0.90

logger = logging.getLogger(__name__)


def disk_used_share():
    """Return how full the media disk is, from 0.0 (empty) to 1.0 (full).

    The media folder appears with the first poster, so until then the
    nearest folder above it that exists is measured (it is the same disk).
    """
    folder = Path(settings.MEDIA_ROOT)
    while not folder.exists():
        folder = folder.parent
    usage = shutil.disk_usage(folder)
    return usage.used / usage.total


def disk_is_nearly_full():
    """Return True (and log why) if new work should stop for lack of space."""
    share = disk_used_share()
    if share >= DISK_STOP:
        logger.error("Disk %.0f%% full: not starting new posts or news.", share * 100)
        return True
    if share >= DISK_WARN:
        logger.warning("Disk %.0f%% full: free some space soon.", share * 100)
    return False
