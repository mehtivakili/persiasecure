from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.cameras.models import Camera, CameraStatus
from apps.events.models import Event
from apps.recordings.models import Recording


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness probe used by Docker/compose and the frontend banner."""
    return Response({"status": "ok", "service": "persiansecure", "time": timezone.now()})


def _org_qs(request, model, org_path="organization"):
    qs = model.objects.all()
    if not request.user.is_superuser:
        qs = qs.filter(**{org_path: request.user.organization})
    return qs


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def summary(request):
    """KPI tiles for the dashboard."""
    cams = _org_qs(request, Camera)
    events = _org_qs(request, Event)
    recs = Recording.objects.all()
    if not request.user.is_superuser:
        recs = recs.filter(camera__organization=request.user.organization)

    by_status = {
        row["status"]: row["n"]
        for row in cams.values("status").annotate(n=Count("id"))
    }
    day_ago = timezone.now() - timedelta(days=1)
    storage = recs.aggregate(total=Sum("size"))["total"] or 0

    org = getattr(request.user, "organization", None)
    return Response(
        {
            "threat_level": org.threat_level if org else "green",
            "cameras": {
                "total": cams.count(),
                "online": by_status.get(CameraStatus.ONLINE, 0),
                "offline": by_status.get(CameraStatus.OFFLINE, 0),
                "disabled": by_status.get(CameraStatus.DISABLED, 0),
                "recording": cams.filter(schedule__mode__in=["continuous", "motion", "scheduled"]).count(),
            },
            "events_24h": events.filter(ts__gte=day_ago).count(),
            "unacknowledged": events.filter(acknowledged=False, cleared=False).count(),
            "recordings_total": recs.count(),
            "storage_bytes": storage,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def events_timeseries(request):
    """Event counts per hour for the last 24h (for the dashboard chart)."""
    events = _org_qs(request, Event)
    since = timezone.now() - timedelta(hours=24)
    buckets = {}
    for ev in events.filter(ts__gte=since).values_list("ts", "type"):
        hour = ev[0].replace(minute=0, second=0, microsecond=0).isoformat()
        buckets.setdefault(hour, 0)
        buckets[hour] += 1
    series = [{"hour": k, "count": v} for k, v in sorted(buckets.items())]
    return Response(series)
