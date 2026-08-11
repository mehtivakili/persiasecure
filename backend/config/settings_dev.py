"""
Native development settings — run the backend WITHOUT Docker.

File-backed SQLite, in-memory channels, LocMem cache and eager Celery (tasks run
inline), so `manage.py runserver` needs no Postgres / Redis / MediaMTX and uses a
few hundred MB instead of Docker's ~6 GB WSL2 VM. Live video + recording still
need MediaMTX + ffmpeg (optional — see docs/dev-native.md).

    python manage.py migrate         --settings=config.settings_dev
    python manage.py createsuperuser --settings=config.settings_dev
    python manage.py runserver       --settings=config.settings_dev

The dev SQLite DB (db.sqlite3) is separate from your Docker/production Postgres —
they never touch each other.
"""
import os
from pathlib import Path

from config.settings import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# File-backed SQLite so dev data persists across restarts (git-ignored).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),  # noqa: F405
    }
}

# No Redis needed natively.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Local folders for uploads + recordings (created on demand).
MEDIA_ROOT = BASE_DIR / "dev_media"  # noqa: F405
RECORDINGS_DIR = os.environ.get("DEV_RECORDINGS_DIR", str(BASE_DIR / "dev_recordings"))  # noqa: F405

for _p in (MEDIA_ROOT, Path(RECORDINGS_DIR)):
    Path(_p).mkdir(parents=True, exist_ok=True)
