"""
Analytics workers.

All detection kinds run from `run_enabled_rules` (celery beat, every 20s):
  motion   — real frame differencing (two frames 1.2s apart, Pillow mean |Δ|)
  tripwire — same diff, but scored only inside a corridor around a user-drawn
             line; a crossing raises a critical alarm with a snapshot
  fire     — colorimetric flame detection on a snapshot (detectors.detect_fire)
  smoke    — desaturated-haze detection on a snapshot (detectors.detect_smoke)
  alpr     — license plates via pluggable detector (+watchlist matching)
  object   — object detection via pluggable detector

Every motion/tripwire diff also feeds the per-camera MotionHeatmap grid.
"""
import glob
import logging
import os
import subprocess
import tempfile

from celery import shared_task
from django.core.files.base import ContentFile

from apps.mediactl import client as media_client
from apps.mediactl import ffmpeg

from . import detectors, heatmap

logger = logging.getLogger(__name__)


@shared_task
def run_enabled_rules():
    """Dispatch each enabled analytics rule to its worker."""
    from django.conf import settings

    if not getattr(settings, "FEATURE_FLAGS", {}).get("analytics", False):
        return 0

    from .models import AnalyticsRule

    dispatched = 0
    for rule in AnalyticsRule.objects.filter(enabled=True, camera__enabled=True).select_related(
        "camera"
    ):
        if rule.kind == "motion":
            motion_worker.delay(
                rule.camera_id,
                sensitivity=float((rule.config or {}).get("sensitivity", 3.0)),
            )
        elif rule.kind == "tripwire":
            tripwire_worker.delay(rule.id)
        elif rule.kind == "fire":
            fire_worker.delay(rule.id)
        elif rule.kind == "smoke":
            smoke_worker.delay(rule.id)
        elif rule.kind == "alpr":
            alpr_worker.delay(rule.id)
        elif rule.kind == "object":
            object_worker.delay(rule.id)
        dispatched += 1
    return dispatched


def _frame_diff(camera, gap_seconds=1.2):
    """
    Grab two frames `gap_seconds` apart; return (diff_L_image, first_frame_jpeg)
    or (None, None). The diff is shared by motion, tripwire and the heatmap.
    """
    url = media_client.build_source_url(camera)
    tmpdir = tempfile.mkdtemp(prefix="diff_")
    pattern = os.path.join(tmpdir, "f%d.jpg")
    cmd = [
        "ffmpeg", "-rtsp_transport", "tcp", "-i", url,
        "-vf", f"fps=1/{gap_seconds},scale=640:-1",
        "-frames:v", "2", "-q:v", "5", pattern,
    ]
    try:
        subprocess.run(
            cmd, timeout=25, check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        frames = sorted(glob.glob(os.path.join(tmpdir, "f*.jpg")))
        if len(frames) < 2:
            return None, None
        from PIL import Image, ImageChops

        with open(frames[0], "rb") as fh:
            first_bytes = fh.read()
        a = Image.open(frames[0]).convert("L")
        b = Image.open(frames[1]).convert("L")
        return ImageChops.difference(a, b), first_bytes
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("frame diff failed for cam %s: %s", camera.id, exc)
        return None, None
    finally:
        for f in glob.glob(os.path.join(tmpdir, "*")):
            try:
                os.remove(f)
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass


def _raise_event(camera, etype, severity, details, snapshot_bytes=None):
    from apps.events.models import Event
    from apps.events.utils import broadcast_event

    ev = Event.objects.create(
        organization=camera.organization,
        camera=camera,
        type=etype,
        severity=severity,
        details=details,
    )
    if snapshot_bytes:
        ev.snapshot.save(f"{etype}_{ev.id}.jpg", ContentFile(snapshot_bytes), save=True)
    broadcast_event(ev)
    return ev


@shared_task
def motion_worker(camera_id, gap_seconds=1.2, sensitivity=3.0):
    """True frame-difference motion detection + heatmap accumulation."""
    from PIL import ImageStat

    from apps.cameras.models import Camera

    camera = Camera.objects.filter(id=camera_id, enabled=True).first()
    if not camera:
        return False
    diff, _first = _frame_diff(camera, gap_seconds)
    if diff is None:
        return False

    heatmap.accumulate(camera, diff)
    score = ImageStat.Stat(diff).mean[0]
    detected = score > sensitivity
    if detected:
        _raise_event(
            camera, "motion", "info",
            {"message": "حرکت تشخیص داده شد.", "score": round(score, 2)},
        )
    return detected


@shared_task
def tripwire_worker(rule_id):
    """Virtual line-crossing: motion localized in a corridor around the line."""
    from .models import AnalyticsRule

    rule = (
        AnalyticsRule.objects.filter(id=rule_id, enabled=True)
        .select_related("camera")
        .first()
    )
    if not rule:
        return False
    config = rule.config or {}
    line = config.get("line")
    if not line or len(line) != 2:
        return False
    sensitivity = float(config.get("sensitivity", 6.0))

    camera = rule.camera
    diff, first = _frame_diff(camera)
    if diff is None:
        return False
    heatmap.accumulate(camera, diff)

    score = heatmap.line_score(diff, line, width_frac=float(config.get("width", 0.05)))
    detected = score > sensitivity
    if detected:
        _raise_event(
            camera, "tripwire", "critical",
            {"message": "عبور از خط تشخیص داده شد.", "score": round(score, 2), "line": line},
            snapshot_bytes=first,
        )
    return detected


@shared_task
def fire_worker(rule_id):
    from .models import AnalyticsRule

    rule = (
        AnalyticsRule.objects.filter(id=rule_id, enabled=True)
        .select_related("camera")
        .first()
    )
    if not rule:
        return False
    camera = rule.camera
    image = ffmpeg.grab_snapshot(media_client.build_source_url(camera))
    if not image:
        return False
    result = detectors.detect_fire(image, rule.config)
    if result.get("detected"):
        _raise_event(
            camera, "fire", "critical",
            {"message": "آتش تشخیص داده شد!", **result},
            snapshot_bytes=image,
        )
        return True
    return False


@shared_task
def smoke_worker(rule_id):
    from .models import AnalyticsRule

    rule = (
        AnalyticsRule.objects.filter(id=rule_id, enabled=True)
        .select_related("camera")
        .first()
    )
    if not rule:
        return False
    camera = rule.camera
    image = ffmpeg.grab_snapshot(media_client.build_source_url(camera))
    if not image:
        return False
    result = detectors.detect_smoke(image, rule.config)
    if result.get("detected"):
        _raise_event(
            camera, "smoke", "critical",
            {"message": "دود تشخیص داده شد!", **result},
            snapshot_bytes=image,
        )
        return True
    return False


@shared_task
def alpr_worker(rule_id):
    from apps.events.models import Event
    from apps.events.utils import broadcast_event

    from .models import AnalyticsRule, PlateRead, PlateWatchlist

    rule = AnalyticsRule.objects.filter(id=rule_id, enabled=True).select_related("camera").first()
    if not rule:
        return 0
    camera = rule.camera
    image = ffmpeg.grab_snapshot(media_client.build_source_url(camera))
    if not image:
        return 0

    plates = detectors.detect_plates(image, rule.config)
    watch = set(
        PlateWatchlist.objects.filter(organization=rule.organization, active=True)
        .values_list("plate", flat=True)
    )
    created = 0
    for p in plates:
        hit = p["plate"] in watch
        ev = Event.objects.create(
            organization=rule.organization, camera=camera, type="alpr",
            severity="critical" if hit else "info",
            details={"plate": p["plate"], "confidence": p["confidence"], "watchlist": hit},
        )
        pr = PlateRead.objects.create(
            organization=rule.organization, camera=camera, plate=p["plate"],
            confidence=p["confidence"], country=p.get("country", "ir"),
            watchlist_hit=hit, event=ev,
        )
        pr.snapshot.save(f"plate_{pr.id}.jpg", ContentFile(image), save=True)
        broadcast_event(ev)
        created += 1
    return created


@shared_task
def object_worker(rule_id):
    from apps.events.models import Event
    from apps.events.utils import broadcast_event

    from .models import AnalyticsRule, ObjectDetection

    rule = AnalyticsRule.objects.filter(id=rule_id, enabled=True).select_related("camera").first()
    if not rule:
        return 0
    camera = rule.camera
    image = ffmpeg.grab_snapshot(media_client.build_source_url(camera))
    if not image:
        return 0

    objs = detectors.detect_objects(image, rule.config)
    created = 0
    for o in objs:
        ev = Event.objects.create(
            organization=rule.organization, camera=camera, type="object",
            severity="warning", details={"label": o["label"], "confidence": o["confidence"]},
        )
        od = ObjectDetection.objects.create(
            organization=rule.organization, camera=camera, label=o["label"],
            confidence=o["confidence"], bbox=o.get("bbox", []), event=ev,
        )
        od.snapshot.save(f"obj_{od.id}.jpg", ContentFile(image), save=True)
        broadcast_event(ev)
        created += 1
    return created
