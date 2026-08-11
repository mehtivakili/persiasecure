"""
Inference runner (Phase AI‑0).

Glue between a `Detector` and the Phase‑7 ingestion pipeline for one camera:

    frame → detector.infer() → RawDetection[] → Detection (contract)
          → ingest_detection()  [threshold + zone + dedup + audit + health]
          → Event → clip → alarm

The runner owns everything that is camera/rule‑specific (which frame, which
class filter, model identity, latency timing); the detector stays pure. If no
active model exists for the task the runner returns `NO_MODEL` so the caller can
fall back to the legacy heuristic path.
"""
import logging
import time

from apps.mediactl import client as media_client
from apps.mediactl import ffmpeg

from ..contract import Detection
from ..pipeline import ingest_detection
from . import overlay, registry

logger = logging.getLogger(__name__)

NO_MODEL = -1  # sentinel: no active DetectorModel for this task


def _log_detections(camera, model_name, raws):
    """Write one log line per detection saying exactly what was found."""
    if not raws:
        logger.info("AI detection — cam %s «%s» (%s): no objects", camera.id, camera.name, model_name)
        return
    from collections import Counter

    counts = Counter(r.label for r in raws)
    summary = "، ".join(f"{count}×{label}" for label, count in counts.most_common())
    logger.info(
        "AI detection — cam %s «%s» (%s): %d object(s) [%s]",
        camera.id, camera.name, model_name, len(raws), summary,
    )


def _frame_dims(image_bytes):
    try:
        import io

        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as im:
            return im.size  # (w, h)
    except Exception:
        return (0, 0)


def infer_frame(detector, image_bytes, width, height):
    """
    Run `detector` on one frame, timing it. Returns (raws, latency_ms). A model
    crash is caught and logged (returns [], latency) so it can never break the
    caller's loop — the whole point of keeping detectors as pure producers.
    """
    t0 = time.perf_counter()
    try:
        raws = detector.infer(image_bytes, width, height)
    except Exception as exc:
        logger.warning("detector %s failed: %s", getattr(detector, "name", "?"), exc)
        raws = []
    latency_ms = (time.perf_counter() - t0) * 1000.0
    return raws, latency_ms


def process_detections(rule, detector, raws, image_bytes, latency_ms=0.0) -> int:
    """
    Map already-inferred `RawDetection`s onto the Phase-7 `Detection` contract
    and ingest each (threshold / zone / dedup / audit / health). Shared by the
    per-snapshot celery path and the continuous decode loop. Returns the number
    of Events created.
    """
    camera = rule.camera
    config = rule.config or {}
    class_filter = set(config.get("classes") or [])

    # What we'd show/alarm on (after the class filter) — publish for the live
    # overlay and log it, so the operator sees per-detection what was found.
    shown = [r for r in raws if not class_filter or r.label in class_filter]
    overlay.publish(camera.id, shown, getattr(detector, "name", ""))
    _log_detections(camera, getattr(detector, "name", ""), shown)

    created = 0
    for r in shown:
        detection = Detection(
            camera_id=camera.id,
            event_type="object",
            confidence=float(r.confidence),
            bounding_boxes=[r.bbox] if r.bbox else [],
            track_id=r.track_id,
            model_name=detector.name,
            model_version=detector.version,
            metadata={"label": r.label, "device": detector.device, **(r.extra or {})},
        )
        event = ingest_detection(detection, rule=rule, snapshot=image_bytes, latency_ms=latency_ms)
        if event is not None:
            created += 1
    return created


def emit_tripwire(tripwire_rule, detector, raw, direction, image_bytes) -> bool:
    """
    Ingest an object-based line-crossing as a critical `tripwire` Event, using
    the tripwire rule's own config (threshold/zone/dedup). Dedup by track_id
    means one crossing = one alarm. Returns True when an Event was created.
    """
    detection = Detection(
        camera_id=tripwire_rule.camera_id,
        event_type="tripwire",
        confidence=float(raw.confidence),
        bounding_boxes=[raw.bbox] if raw.bbox else [],
        track_id=raw.track_id,
        model_name=getattr(detector, "name", ""),
        model_version=getattr(detector, "version", ""),
        metadata={
            "label": raw.label,
            "direction": direction,
            "line": (tripwire_rule.config or {}).get("line"),
            "message": "عبور از خط تشخیص داده شد.",
        },
    )
    event = ingest_detection(detection, rule=tripwire_rule, snapshot=image_bytes)
    return event is not None


def run_object_detection(rule) -> int:
    """
    Per-snapshot path (celery `object_worker`): grab one frame from `rule.camera`,
    run the active object model, ingest survivors. Returns Events created, or
    NO_MODEL when no active object model exists (caller falls back to legacy).
    """
    detector = registry.get_detector("object")
    if detector is None:
        return NO_MODEL

    camera = rule.camera
    image = ffmpeg.grab_snapshot(media_client.build_source_url(camera))
    if not image:
        return 0
    width, height = _frame_dims(image)
    raws, latency_ms = infer_frame(detector, image, width, height)
    return process_detections(rule, detector, raws, image, latency_ms)


def run_alpr_detection(rule) -> int:
    """
    Per-snapshot ALPR path: run the active plate model on one frame, normalize
    each read to canonical Iranian form, match the org watchlist (a hit → a
    critical alarm), and persist a `PlateRead` linked to the Event. Returns
    plates recorded, or NO_MODEL when no active ALPR model exists.
    """
    from django.core.cache import cache
    from django.core.files.base import ContentFile

    from apps.events.models import Event
    from apps.events.utils import broadcast_event

    from ..models import PlateRead, PlateWatchlist
    from ..pipeline import DEDUP_WINDOW_SECONDS, record_detector_health
    from .plates import normalize_plate, parse_iranian_plate

    detector = registry.get_detector("alpr")
    if detector is None:
        return NO_MODEL

    camera = rule.camera
    image = ffmpeg.grab_snapshot(media_client.build_source_url(camera))
    if not image:
        return 0
    width, height = _frame_dims(image)
    raws, latency_ms = infer_frame(detector, image, width, height)
    record_detector_health(detector.name, detector.version, latency_ms)

    config = rule.config or {}
    try:
        min_conf = float(config.get("min_confidence", 0.0))
    except (TypeError, ValueError):
        min_conf = 0.0
    require_valid = bool(config.get("require_valid_format", False))

    watch = set(
        PlateWatchlist.objects.filter(organization=rule.organization, active=True)
        .values_list("plate", flat=True)
    )
    created = 0
    for r in raws:
        if r.confidence < min_conf:
            continue
        raw_plate = (r.extra or {}).get("plate", "")
        parsed = parse_iranian_plate(raw_plate)
        plate = parsed["canonical"] if parsed else normalize_plate(raw_plate)
        if not plate or (require_valid and not parsed):
            continue

        dedup_key = f"alpr_dedup_{camera.id}_{plate}"
        if cache.get(dedup_key):
            continue
        cache.set(dedup_key, 1, timeout=int(config.get("dedup_seconds", DEDUP_WINDOW_SECONDS)))

        hit = plate in watch
        event = Event.objects.create(
            organization=rule.organization, camera=camera, type="alpr",
            severity="critical" if hit else "info",
            details={
                "plate": plate,
                "pretty": parsed["pretty"] if parsed else plate,
                "confidence": round(float(r.confidence), 3),
                "watchlist": hit,
                "valid_format": bool(parsed),
                "model_name": detector.name,
                "model_version": detector.version,
            },
        )
        pr = PlateRead.objects.create(
            organization=rule.organization, camera=camera, plate=plate,
            confidence=round(float(r.confidence) * 100, 1), country="ir",
            watchlist_hit=hit, event=event,
        )
        if image:
            pr.snapshot.save(f"plate_{pr.id}.jpg", ContentFile(image), save=True)
        broadcast_event(event)
        created += 1
    return created
