"""Local settings for running the source checkout as a standalone Django site."""

from pathlib import Path

from .settings import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
DEV_BASE_DIR = Path(__file__).resolve().parents[1]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": DEV_BASE_DIR / "dev.sqlite3",
}}
