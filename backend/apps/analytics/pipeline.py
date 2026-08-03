"""
Detection ingestion pipeline (Phase 7).

Turns a contract `Detection` into an `Event` (which then flows through the normal
alarm feed + event‑clip machinery) after applying operator controls:
  * per‑camera **confidence threshold** (rule.config.min_confidence)
  * **detection zone** (rule.config.zone polygon) — ignore detections outside it
  * **duplicate suppression** (per camera + type + track, time‑windowed)
  * **model auditability** — model name/version + confidence + boxes stored on the
    event, and per‑detector **health/latency** recorded for monitoring.

Runs inside the isolated `ai` Celery queue, so inference can never delay
recording, exports, health checks or alarms.
"""
import logging

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

DEDUP_WINDOW_SECONDS = 30
_HEALTH_KEY = "detector_health"

# Map a detection type onto an alarm severity.
_SEVERITY_BY_TYPE = {
    "fire": "critical",
    "smoke": "critical",
    "tripwire": "critical",
    "face": "warning",
    "object": "warning",
    "alpr": "info",
    "motion": "info",
}


def _point_in_polygon(x, y, poly):
    """Ray‑casting point‑in‑polygon; poly = [[x,y], ...] normalized 0..1."""
    if not poly or len(poly) < 3:
        return True
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i][0], poly[i][1]
        xj, yj = poly[j][0], poly[j][1]
        denom = (yj - yi) or 1e-9
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / denom + xi):
            inside = not inside
        j = i
    return inside


def _passes_zone(boxes, zone):
    if not zone:
        return True
    if not boxes:  # no bbox → treat as whole frame
        return True
    for b in boxes:
        if len(b) >= 4:
            cx, cy = b[0] + b[2] / 2.0, b[1] + b[3] / 2.0
        elif len(b) >= 2:
            cx, cy = b[0], b[1]
        else:
            continue
        if _point_in_polygon(cx, cy, zone):
            return True
    return False


def _rule_config(rule):
    return rule.config if (rule and isinstance(rule.config, dict)) else {}


def record_detector_health(model_name, model_version, latency_ms):
    """Accumulate per‑model run count, avg latency and last‑seen for monitoring."""
    data = cache.get(_HEALTH_KEY) or {}
    name = model_name or "unknown"
    prev = data.get(name, {"runs": 0, "avg_latency_ms": 0.0})
    runs = prev["runs"] + 1
    avg = (prev["avg_latency_ms"] * prev["runs"] + float(latency_ms)) / runs
    data[name] = {
        "version": model_version or "",
        "runs": runs,
        "avg_latency_ms": round(avg, 1),
        "last_run": timezone.now().isoformat(),
    }
    cache.set(_HEALTH_KEY, data, timeout=3600)


def detector_health():
    return cache.get(_HEALTH_KEY) or {}


def ingest_detection(detection, rule=None, snapshot=None, latency_ms=0.0):
    """
    Apply threshold/zone/dedup and, if the detection survives, create an Event.
    Returns the Event, or None when the detection was filtered out.
    """
    from apps.cameras.models import Camera
    from apps.events.models import Event
    from apps.events.utils import broadcast_event

    record_detector_health(detection.model_name, detection.model_version, latency_ms)

    config = _rule_config(rule)

    # 1. Confidence threshold.
    try:
        threshold = float(config.get("min_confidence", 0.0))
    except (TypeError, ValueError):
        threshold = 0.0
    if detection.confidence < threshold:
        return None

    # 2. Detection zone.
    if not _passes_zone(detection.bounding_boxes, config.get("zone")):
        return None

    # 3. Duplicate suppression.
    track = detection.track_id or str((detection.metadata or {}).get("label", ""))
    dedup_key = f"det_dedup_{detection.camera_id}_{detection.event_type}_{track}"
    if cache.get(dedup_key):
        return None
    try:
        window = int(config.get("dedup_seconds", DEDUP_WINDOW_SECONDS))
    except (TypeError, ValueError):
        window = DEDUP_WINDOW_SECONDS
    cache.set(dedup_key, 1, timeout=window)

    camera = Camera.objects.filter(id=detection.camera_id).first()
    if camera is None:
        return None

    details = {
        "confidence": round(float(detection.confidence), 3),
        "model_name": detection.model_name,
        "model_version": detection.model_version,
        "bounding_boxes": detection.bounding_boxes,
        "track_id": detection.track_id,
        **(detection.metadata or {}),
    }
    event = Event.objects.create(
        organization=camera.organization,
        camera=camera,
        type=detection.event_type,
        severity=_SEVERITY_BY_TYPE.get(detection.event_type, "warning"),
        details=details,
    )
    if snapshot:
        from django.core.files.base import ContentFile

        event.snapshot.save(f"{detection.event_type}_{event.id}.jpg", ContentFile(snapshot), save=True)
    broadcast_event(event)
    return event
