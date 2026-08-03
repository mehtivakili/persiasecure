"""Celery tasks: index recorded segments, apply retention, build exports,
evaluate weekly schedules, watch storage and assemble event clips."""
import hashlib
import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone as dt_timezone

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# A file whose mtime is younger than this is assumed to still be written by
# MediaMTX; skip it until it settles so we index only complete segments.
_MIN_SETTLE_SECONDS = 5

# MediaMTX writes files like: /recordings/cam_12/2026-07-06_10-15-30-000000.mp4
_TS_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})")


def _parse_start(filename):
    m = _TS_RE.search(filename)
    if not m:
        return None
    y, mo, d, h, mi, s = map(int, m.groups())
    # MediaMTX writes segment filenames in the recorder container's local time,
    # which is UTC (the mediamtx container has no TZ set). Interpret them as UTC —
    # NOT the Django TIME_ZONE (Asia/Tehran) — otherwise every recording lands
    # 3.5h away from its event, breaking the timeline alignment and event clips.
    return datetime(y, mo, d, h, mi, s, tzinfo=dt_timezone.utc)


@shared_task
def index_recordings():
    """Scan the recordings volume and create Recording rows for new segments."""
    from apps.cameras.models import Camera
    from .models import Recording

    root = settings.RECORDINGS_DIR
    if not os.path.isdir(root):
        return 0

    created = 0
    for entry in os.scandir(root):
        if not entry.is_dir() or not entry.name.startswith("cam_"):
            continue
        try:
            cam_id = int(entry.name.split("_", 1)[1])
        except ValueError:
            continue
        camera = Camera.objects.filter(id=cam_id).first()
        if not camera:
            continue
        for f in os.scandir(entry.path):
            if not f.is_file() or not f.name.endswith((".mp4", ".ts")):
                continue
            start = _parse_start(f.name)
            if not start:
                continue
            st = f.stat()
            # Skip empty or still-being-written files so we index whole segments.
            if st.st_size == 0 or (time.time() - st.st_mtime) < _MIN_SETTLE_SECONDS:
                continue
            duration = _probe_duration(f.path)
            # Idempotent + race-safe: unique file_path means a concurrent indexer
            # can't create a duplicate; get_or_create swallows the race.
            _, was_created = Recording.objects.get_or_create(
                file_path=f.path,
                defaults={
                    "camera": camera,
                    "start": start,
                    "end": start + timedelta(seconds=duration) if duration else None,
                    "size": st.st_size,
                    "duration": duration,
                    "status": Recording.Status.COMPLETE,
                },
            )
            if was_created:
                created += 1
    if created:
        logger.info("index_recordings: %s new segments", created)
    return created


@shared_task
def evaluate_schedules():
    """
    Toggle MediaMTX recording for `scheduled` cameras as their weekly windows
    open and close. Runs every minute; reconcile is idempotent so re-applying a
    steady state is a cheap no-op patch.
    """
    from apps.recordings.models import RecordingSchedule

    from . import services

    count = 0
    for sched in RecordingSchedule.objects.filter(
        mode=RecordingSchedule.Mode.SCHEDULED, camera__enabled=True
    ).select_related("camera"):
        services.reconcile_recording(sched.camera)
        count += 1
    return count


@shared_task
def check_storage():
    """
    Watch the recordings volume and raise a throttled storage alarm Event when
    free space drops below the configured thresholds (Phase 2 operations).
    """
    from django.core.cache import cache

    from apps.accounts.models import Organization
    from apps.events.models import Event, EventType, Severity

    root = settings.RECORDINGS_DIR
    if not os.path.isdir(root):
        return {}

    usage = shutil.disk_usage(root)
    free_gb = usage.free / 1e9
    free_ratio = usage.free / usage.total if usage.total else 1.0
    min_free_gb = float(getattr(settings, "STORAGE_MIN_FREE_GB", 5))
    warn_ratio = float(getattr(settings, "STORAGE_WARN_FREE_RATIO", 0.10))

    severity = None
    if free_gb < min_free_gb:
        severity = Severity.CRITICAL
    elif free_ratio < warn_ratio:
        severity = Severity.WARNING

    result = {
        "free_gb": round(free_gb, 1),
        "free_ratio": round(free_ratio, 3),
        "alarm": severity or "",
    }
    if not severity:
        cache.delete("storage_alarm_level")
        return result

    # Throttle: one alarm per severity per hour so we don't flood the feed.
    if cache.get("storage_alarm_level") == severity:
        return result
    cache.set("storage_alarm_level", severity, timeout=3600)

    for org in Organization.objects.filter(is_active=True):
        Event.objects.create(
            organization=org,
            type=EventType.STORAGE,
            severity=severity,
            details={
                "message": "فضای ذخیره‌سازی رو به اتمام است.",
                "free_gb": round(free_gb, 1),
                "free_ratio": round(free_ratio, 3),
            },
        )
    logger.warning("check_storage: %s free (%.1f GB)", severity, free_gb)
    return result


@shared_task
def apply_retention():
    """
    Delete ordinary Recording rows + files older than each camera's retention
    window. Protected segments (evidence / legal hold) are kept regardless of
    age; exports live outside the indexed segments and are untouched here.
    """
    from .models import EventClip, Recording, RecordingSchedule

    removed = 0
    for sched in RecordingSchedule.objects.select_related("camera"):
        cutoff = timezone.now() - timedelta(days=sched.retention_days)
        old = Recording.objects.filter(
            camera=sched.camera, start__lt=cutoff, protected=False
        )
        # Never delete a segment still needed by a clip that hasn't assembled yet.
        pending = list(
            EventClip.objects.filter(
                camera=sched.camera,
                status__in=[EventClip.Status.PENDING, EventClip.Status.ASSEMBLING],
            ).values_list("start", "end")
        )
        for rec in old:
            rec_end = rec.end or rec.start
            if any(rec.start < w_end and rec_end > w_start for w_start, w_end in pending):
                continue
            try:
                if os.path.exists(rec.file_path):
                    os.remove(rec.file_path)
            except OSError:
                pass
            rec.delete()
            removed += 1
    if removed:
        logger.info("apply_retention: removed %s recordings", removed)
    return removed


@shared_task
def build_export(job_id):
    """Concatenate/cut recordings covering a time range into one mp4."""
    from .models import ExportJob, Recording

    job = ExportJob.objects.filter(id=job_id).first()
    if not job:
        return
    job.status = ExportJob.Status.RUNNING
    job.save(update_fields=["status"])

    # Overlap filter: include any segment that touches the requested range.
    segments = [
        s
        for s in Recording.objects.filter(
            camera=job.camera, start__lt=job.end, end__gt=job.start
        ).order_by("start")
        if os.path.exists(s.file_path)
    ]
    if not segments:
        job.status = ExportJob.Status.FAILED
        job.save(update_fields=["status"])
        return

    out_dir = os.path.join(settings.RECORDINGS_DIR, "exports")
    os.makedirs(out_dir, exist_ok=True)
    list_file = os.path.join(out_dir, f"job_{job.id}.txt")
    out_file = os.path.join(out_dir, f"export_{job.id}.mp4")
    with open(list_file, "w") as fh:
        for seg in segments:
            fh.write(f"file '{seg.file_path}'\n")

    # Trim to the EXACT requested range (issue #7): seek past the leading part of
    # the first segment and cap the duration. Re-encoding to H.264 makes the cut
    # frame-accurate and the output universally playable (incl. HEVC sources).
    offset = max(0.0, (job.start - segments[0].start).total_seconds())
    duration = (job.end - job.start).total_seconds()
    try:
        _ffmpeg_trim(list_file, offset, duration, out_file)
        job.output_file = out_file
        job.size = os.path.getsize(out_file) if os.path.exists(out_file) else 0
        job.sha256 = _sha256(out_file) if job.size else ""  # evidence integrity
        job.status = ExportJob.Status.DONE
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("export %s failed: %s", job.id, exc)
        job.status = ExportJob.Status.FAILED
    finally:
        job.save(update_fields=["output_file", "size", "sha256", "status"])
        try:
            os.remove(list_file)
        except OSError:
            pass


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ffmpeg_trim(list_file, offset, duration, out_file):
    """Concat the segment list, trim to [offset, offset+duration], H.264 output.

    `-threads 2` caps each encode's CPU so several concurrent clip/export jobs
    can't saturate the whole machine (paired with a small Celery --concurrency).
    """
    cmd = [
        "ffmpeg", "-y", "-threads", "2", "-f", "concat", "-safe", "0", "-i", list_file,
        "-ss", f"{offset:.3f}", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an",
        "-movflags", "+faststart", out_file,
    ]
    subprocess.run(cmd, timeout=600, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.exists(out_file)


@shared_task(bind=True, max_retries=5, default_retry_delay=10)
def assemble_event_clip(self, clip_id):
    """
    Assemble the MP4 for an EventClip from the rolling recording buffer:
    wait for the trailing segment, concat the overlapping segments, trim exactly
    to the pre/post window, then record size/duration/sha256. Retries while the
    final segment is still being written; marks the clip failed if no footage
    ever appears. Notifies the frontend on completion.
    """
    from apps.events.utils import broadcast_event

    from .models import EventClip, Recording

    clip = (
        EventClip.objects.filter(id=clip_id).select_related("camera", "event").first()
    )
    if clip is None or clip.status == EventClip.Status.READY:
        return
    clip.status = EventClip.Status.ASSEMBLING
    clip.attempts = (clip.attempts or 0) + 1
    clip.save(update_fields=["status", "attempts"])

    segments = list(
        Recording.objects.filter(
            camera=clip.camera, start__lt=clip.end, end__gt=clip.start
        ).order_by("start")
    )

    # Wait for the trailing segment (the one covering clip.end) to be indexed.
    last_covered = segments and segments[-1].end and segments[-1].end >= clip.end
    if not last_covered and self.request.retries < self.max_retries:
        raise self.retry(countdown=10)

    existing = [s for s in segments if os.path.exists(s.file_path)]
    if not existing:
        return _fail_clip(clip, "بدون قطعهٔ ضبط برای این بازه.", broadcast_event)

    out_dir = os.path.join(settings.RECORDINGS_DIR, "clips")
    os.makedirs(out_dir, exist_ok=True)
    list_file = os.path.join(out_dir, f"clip_{clip.id}.txt")
    out_file = os.path.join(out_dir, f"clip_{clip.id}.mp4")
    with open(list_file, "w") as fh:
        for seg in existing:
            fh.write(f"file '{seg.file_path}'\n")

    offset = max(0.0, (clip.start - existing[0].start).total_seconds())
    duration = (clip.end - clip.start).total_seconds()
    try:
        ok = _ffmpeg_trim(list_file, offset, duration, out_file)
        if not ok:
            return _fail_clip(clip, "ffmpeg خروجی تولید نکرد.", broadcast_event)
        clip.file_path = out_file
        clip.size = os.path.getsize(out_file)
        clip.duration = _probe_duration(out_file) or duration
        clip.sha256 = _sha256(out_file)
        clip.error = ""
        clip.status = EventClip.Status.READY
        clip.save(update_fields=["file_path", "size", "duration", "sha256", "error", "status"])
    except (subprocess.SubprocessError, OSError) as exc:
        return _fail_clip(clip, str(exc)[:255], broadcast_event)
    finally:
        try:
            os.remove(list_file)
        except OSError:
            pass

    broadcast_event(clip.event)
    logger.info("assemble_event_clip: clip %s ready (%.1fs)", clip.id, clip.duration)
    return clip.id


def _fail_clip(clip, message, broadcast):
    from .models import EventClip

    clip.status = EventClip.Status.FAILED
    clip.error = message
    clip.save(update_fields=["status", "error"])
    try:
        broadcast(clip.event)
    except Exception:  # pragma: no cover - notification best effort
        pass
    logger.warning("assemble_event_clip: clip %s failed: %s", clip.id, message)
    return None


def _probe_codec(path):
    """Return the video codec name of a media file (e.g. 'h264', 'hevc')."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=20,
        )
        return (out.stdout or "").strip().lower()
    except subprocess.SubprocessError:
        return ""


def _probe_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=20,
        )
        return float(out.stdout.strip() or 0)
    except (subprocess.SubprocessError, ValueError):
        return 0.0
