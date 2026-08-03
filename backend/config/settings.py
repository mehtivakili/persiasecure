"""
Django settings for PersianSecure (سامانه نظارت تصویری ابری فارسی).

Reads configuration from environment variables so the same image runs in
Docker Compose and in local development. Falls back to SQLite when no
Postgres host is configured, so `python manage.py runserver` works locally.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from the repo root when developing locally.
load_dotenv(BASE_DIR.parent / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(int(default))).lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1") or ["*"]
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost,http://localhost:5173"
)

AUTH_USER_MODEL = "accounts.User"

# Product availability flags. Phase-2 modules remain installed so their
# migrations and data are preserved, but the API tells clients not to present
# them until an operator explicitly enables each capability.
FEATURE_FLAGS = {
    "analytics": env_bool("FEATURE_ANALYTICS", False),
    "access_control": env_bool("FEATURE_ACCESS_CONTROL", False),
    "maps": env_bool("FEATURE_MAPS", False),
    "federation": env_bool("FEATURE_FEDERATION", False),
    "evidence": env_bool("FEATURE_EVIDENCE", False),
}

# Synthetic detector output is never allowed implicitly. This is separate
# from FEATURE_ANALYTICS: a deployment can expose analytics backed by real
# detectors while keeping random demo fixtures disabled.
ENABLE_DEMO_ANALYTICS = env_bool("ENABLE_DEMO_ANALYTICS", False)

# Key used to encrypt camera credentials at rest (apps.cameras.crypto).
# Prefer a real Fernet key in production (Fernet.generate_key()); when empty a
# key is derived from SECRET_KEY so development needs no extra config. Keep it
# STABLE and BACKED UP — losing it makes stored camera passwords unrecoverable.
CREDENTIAL_ENCRYPTION_KEY = os.environ.get("CREDENTIAL_ENCRYPTION_KEY", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "corsheaders",
    "django_filters",
    "channels",
    "django_celery_beat",
    # Local apps
    "apps.accounts",
    "apps.cameras",
    "apps.recordings",
    "apps.events",
    "apps.dashboard",
    "apps.analytics",
    "apps.mediactl",
    # Phase 2
    "apps.access",
    "apps.maps",
    "apps.federation",
    "apps.evidence",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "persiansecure"),
            "USER": os.environ.get("POSTGRES_USER", "persiansecure"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "persiansecure"),
            "HOST": os.environ.get("POSTGRES_HOST", "postgres"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Cache / Channels / Celery (Redis)
# ---------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

# Shared cache — used for cross-service signals like the celery heartbeat.
if os.environ.get("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}
# In-memory channel layer fallback for local dev without Redis.
if not os.environ.get("REDIS_URL") and DEBUG:
    CHANNEL_LAYERS["default"] = {"BACKEND": "channels.layers.InMemoryChannelLayer"}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_EAGER", False)
CELERY_TIMEZONE = "Asia/Tehran"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# ---------------------------------------------------------------------------
# DRF / Auth
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    # Only the login endpoint is throttled (scope "login"); everything else is
    # unthrottled so dashboards/polling aren't affected.
    "DEFAULT_THROTTLE_RATES": {
        "login": os.environ.get("LOGIN_THROTTLE_RATE", "10/min"),
    },
}

from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# i18n / tz — Persian first, RTL
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True
LANGUAGES = [("fa", "فارسی"), ("en", "English")]

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# PersianSecure / media server integration
# ---------------------------------------------------------------------------
MEDIAMTX = {
    "API_URL": os.environ.get("MEDIAMTX_API_URL", "http://mediamtx:9997"),
    # Default to SAME-ORIGIN relative paths (nginx proxies /hls and /webrtc to
    # MediaMTX). Relative URLs make one build work in every deployment mode —
    # localhost, an on-prem LAN server (VMS), or a cloud domain (VSaaS) — and
    # over HTTPS. Only override with absolute URLs for exotic split setups.
    # `or` (not the get() default) so an empty env var also falls back.
    "HLS_URL": os.environ.get("MEDIAMTX_HLS_URL") or "/hls",
    "WEBRTC_URL": os.environ.get("MEDIAMTX_WEBRTC_URL") or "/webrtc",
    "RTSP_HOST": os.environ.get("MEDIAMTX_RTSP_HOST") or "mediamtx",
    "RTSP_PORT": os.environ.get("MEDIAMTX_RTSP_PORT") or "8554",
}
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", str(BASE_DIR / "recordings"))

# Recording policy tuning (Phase 2).
# Motion mode records a short-segment rolling buffer so pre-event video exists.
MOTION_BUFFER_SECONDS = int(os.environ.get("MOTION_BUFFER_SECONDS", "6"))
# Low-storage alarm thresholds for the recordings volume.
STORAGE_MIN_FREE_GB = float(os.environ.get("STORAGE_MIN_FREE_GB", "5"))
STORAGE_WARN_FREE_RATIO = float(os.environ.get("STORAGE_WARN_FREE_RATIO", "0.10"))
# Lifetime of the signed playback URLs handed to the browser (seconds).
PLAYBACK_URL_TTL = int(os.environ.get("PLAYBACK_URL_TTL", str(6 * 3600)))

# SMS / voice-call notifications (apps.events.notify).
# provider "console" logs messages — works with no account; set kavenegar/twilio + keys in .env.
NOTIFY = {
    "PROVIDER": os.environ.get("SMS_PROVIDER", "console"),
    "KAVENEGAR_API_KEY": os.environ.get("KAVENEGAR_API_KEY", ""),
    "SMS_SENDER": os.environ.get("SMS_SENDER", ""),
    "TWILIO_ACCOUNT_SID": os.environ.get("TWILIO_ACCOUNT_SID", ""),
    "TWILIO_AUTH_TOKEN": os.environ.get("TWILIO_AUTH_TOKEN", ""),
    "TWILIO_FROM": os.environ.get("TWILIO_FROM", ""),
}
