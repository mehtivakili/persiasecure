"""System health monitor (Genetec Health-Monitor-style) — service + storage checks."""
import shutil
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Max, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

HEARTBEAT_KEY = "celery_heartbeat"


def _check_db():
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False


def _check_redis():
    try:
        import redis

        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=3)
        return bool(r.ping())
    except Exception:
        return False


def _check_mediamtx():
    try:
        r = requests.get(
            f"{settings.MEDIAMTX['API_URL'].rstrip('/')}/v3/config/paths/list", timeout=3
        )
        return r.status_code == 200
    except requests.RequestException:
        return False


def _check_celery():
    """The periodic health_check task stamps a heartbeat in the shared cache."""
    ts = cache.get(HEARTBEAT_KEY)
    if not ts:
        return False
    return (timezone.now() - ts).total_seconds() < 120


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def system_health(request):
    if not request.user.has_vms_perm("system.view"):
        return Response({"detail": "عدم دسترسی."}, status=403)

    from apps.cameras.models import Camera
    from apps.recordings.models import Recording

    org_filter = {} if request.user.is_superuser else {"organization": request.user.organization}
    cams = Camera.objects.filter(**org_filter)
    recs = Recording.objects.all()
    if not request.user.is_superuser:
        recs = recs.filter(camera__organization=request.user.organization)

    try:
        du = shutil.disk_usage(settings.RECORDINGS_DIR)
        disk = {"total": du.total, "used": du.used, "free": du.free}
    except OSError:
        disk = {"total": 0, "used": 0, "free": 0}

    by_status = {}
    for c in cams.values_list("status", flat=True):
        by_status[c] = by_status.get(c, 0) + 1

    # Storage usage per camera (top consumers).
    storage_by_camera = [
        {"camera": row["camera"], "name": row["camera__name"], "bytes": row["bytes"] or 0}
        for row in recs.values("camera", "camera__name").annotate(bytes=Sum("size")).order_by("-bytes")[:50]
    ]
    total_bytes = sum(c["bytes"] for c in storage_by_camera)

    # Projected days remaining = free space / bytes ingested in the last 24h.
    recent_bytes = recs.filter(start__gte=timezone.now() - timedelta(days=1)).aggregate(
        s=Sum("size")
    )["s"] or 0
    projected_days = round(disk["free"] / recent_bytes, 1) if recent_bytes else None

    # Recording delay: seconds since the newest indexed segment (staleness signal).
    last_start = recs.aggregate(m=Max("start"))["m"]
    recording_delay = int((timezone.now() - last_start).total_seconds()) if last_start else None

    return Response(
        {
            "services": {
                "database": _check_db(),
                "redis": _check_redis(),
                "mediamtx": _check_mediamtx(),
                "celery": _check_celery(),
            },
            "disk": disk,
            "recordings": {"count": recs.count(), "bytes": total_bytes},
            "storage_by_camera": storage_by_camera,
            "projected_days": projected_days,
            "recording_delay_seconds": recording_delay,
            "cameras": by_status,
            "time": timezone.now(),
        }
    )
