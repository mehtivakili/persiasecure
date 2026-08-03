"""Test settings: in-memory SQLite, eager Celery, in-memory channels.

Run with:  python manage.py test --settings=config.settings_test
Keeps tests independent of Postgres/Redis/MediaMTX.
"""
from config.settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CELERY_TASK_ALWAYS_EAGER = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Disable the login rate limit under test — the suite logs in on nearly every
# APITestCase setUp from one IP, which would otherwise trip the throttle.
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"login": None}}
