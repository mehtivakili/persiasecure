"""
Live detection overlay (per-camera latest boxes).

Every time a detector runs on a camera's frame, the class-filtered boxes are
published to a short-lived cache entry. The live-view overlay endpoint reads it
so the frontend can draw the current bounding boxes on top of the video. Kept in
the cache (not the DB): it is ephemeral "what is on screen right now" data, not an
audit record — the Events created by `ingest_detection` remain the durable record.
"""
from django.core.cache import cache
from django.utils import timezone

TTL_SECONDS = 30


def _key(camera_id):
    return f"ai_overlay_{camera_id}"


def publish(camera_id, raws, model_name=""):
    """Store the latest frame's detections for a camera (RawDetection list)."""
    cache.set(
        _key(camera_id),
        {
            "ts": timezone.now().isoformat(),
            "model": model_name or "",
            "detections": [
                {
                    "label": r.label,
                    "confidence": round(float(r.confidence), 3),
                    "bbox": [round(float(v), 4) for v in (r.bbox or [])],
                    "track_id": r.track_id,
                }
                for r in raws
            ],
        },
        timeout=TTL_SECONDS,
    )


def latest(camera_id):
    """The most recent published detections for a camera, or None."""
    return cache.get(_key(camera_id))
