"""
Event → clip orchestration (Phase 3).

Decides whether an Event should produce a video clip, computes its pre/post
window, deduplicates overlapping events from the same camera, creates the
EventClip row (in the event's transaction) and queues assembly *after commit* so
the worker never races the database.
"""
import logging
from datetime import timedelta

from django.db import transaction

from .models import EventClip, RecordingSchedule

logger = logging.getLogger(__name__)

# Event types that have camera video worth clipping. System events like
# `offline`/`storage` have no footage and are skipped.
CLIP_EVENT_TYPES = {
    "motion", "tripwire", "fire", "smoke", "alpr", "object", "manual", "tamper",
}


def _recording_configured(camera):
    sched = getattr(camera, "schedule", None)
    return bool(sched and sched.mode != RecordingSchedule.Mode.OFF)


def schedule_clip_for_event(event):
    """
    Create + queue an EventClip for a qualifying event. Returns the clip, an
    existing overlapping clip (dedup), or None when the event isn't clip-worthy.
    Safe to call from an Event post_save signal.
    """
    if not event.camera_id or event.type not in CLIP_EVENT_TYPES:
        return None

    camera = event.camera
    if not _recording_configured(camera):
        # No rolling buffer / continuous recording → there is no footage to clip.
        return None

    sched = camera.schedule
    start = event.ts - timedelta(seconds=sched.pre_event_seconds)
    end = event.ts + timedelta(seconds=sched.post_event_seconds)

    # Dedup: merge with an existing (non-failed) clip whose window overlaps, so a
    # burst of motion events on one camera yields a single clip.
    existing = EventClip.objects.filter(
        camera=camera,
        status__in=[
            EventClip.Status.PENDING,
            EventClip.Status.ASSEMBLING,
            EventClip.Status.READY,
        ],
        start__lt=end,
        end__gt=start,
    ).first()
    if existing:
        return existing

    clip = EventClip.objects.create(
        event=event, camera=camera, start=start, end=end, status=EventClip.Status.PENDING
    )

    # Queue assembly after the post-event window has elapsed (so the trailing
    # segment exists) and only once the surrounding transaction has committed.
    delay = sched.post_event_seconds + sched.segment_seconds + 5
    clip_id = clip.id

    def _queue():
        from .tasks import assemble_event_clip

        assemble_event_clip.apply_async((clip_id,), countdown=delay)

    transaction.on_commit(_queue)
    return clip
