#!/usr/bin/env python
"""Run Django's command-line tools, for example: python manage.py migrate."""

import os
import sys


def main():
    """Pick the settings file and run the requested Django command."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
