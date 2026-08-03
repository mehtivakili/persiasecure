"""
Recording control services.

Single source of truth for "should this camera be recording right now?" — the
answer combines the weekly RecordingSchedule, the current time (for `scheduled`
mode), and any active manual session, and is what gets pushed to MediaMTX.
Keeping this in one place lets camera edits, schedule edits, the schedule
evaluator and the manual Start/Stop button all reconcile the same way (Phase 2).

Mode semantics:
  off         → never records
  continuous  → always records (segment_seconds segments)
  scheduled   → records only inside the weekly windows (org timezone)
  motion      → always records a SHORT-segment rolling buffer (so pre-event
                video exists); event-clip preservation is Phase 3
  manual      → records while an operator ManualRecordingSession is active
"""
from django.conf import settings
from django.utils import timezone

from apps.mediactl import client as media_client

from .models import ManualRecordingSession, RecordingSchedule


def _schedule(camera):
    return getattr(camera, "schedule", None)


# ---------------------------------------------------------------------------
# Weekly window evaluation (scheduled mode)
# ---------------------------------------------------------------------------
# weekly = {"<0-6>": [{"from": "HH:MM", "to": "HH:MM"}, ...]} where the day index
# is the Persian week: 0=Saturday … 6=Friday (matches the RTL UI). A window whose
# `from` > `to` wraps past midnight into the next day.

def _parse_hhmm(value):
    try:
        h, m = str(value).split(":")
        minutes = int(h) * 60 + int(m)
        return minutes if 0 <= minutes <= 24 * 60 else None
    except (ValueError, AttributeError):
        return None


def _persian_index(dt):
    # Python weekday(): Mon=0..Sun=6. Persian week starts Saturday.
    return (dt.weekday() + 2) % 7


def within_weekly_window(weekly, now=None):
    if not weekly:
        return False
    local = timezone.localtime(now or timezone.now())
    t = local.hour * 60 + local.minute
    today = str(_persian_index(local))
    yesterday = str((_persian_index(local) - 1) % 7)

    for w in weekly.get(today, []) or []:
        frm, to = _parse_hhmm(w.get("from")), _parse_hhmm(w.get("to"))
        if frm is None or to is None or frm == to:
            continue
        if frm < to and frm <= t < to:
            return True
        if frm > to and t >= frm:  # window opened today, runs past midnight
            return True
    # A window that opened yesterday and wraps into today.
    for w in weekly.get(yesterday, []) or []:
        frm, to = _parse_hhmm(w.get("from")), _parse_hhmm(w.get("to"))
        if frm is None or to is None:
            continue
        if frm > to and t < to:
            return True
    return False


def segment_seconds(camera):
    """Segment length pushed to MediaMTX. Motion uses a short rolling buffer."""
    sched = _schedule(camera)
    if sched and sched.mode == RecordingSchedule.Mode.MOTION:
        return int(getattr(settings, "MOTION_BUFFER_SECONDS", 6))
    return sched.segment_seconds if sched else 60


def active_manual_session(camera):
    return ManualRecordingSession.objects.filter(
        camera=camera, status=ManualRecordingSession.Status.RECORDING
    ).first()


def should_record(camera, now=None):
    """Effective record state at `now`: schedule/window OR active manual session."""
    if active_manual_session(camera) is not None:
        return True
    sched = _schedule(camera)
    if not sched:
        return False
    mode = sched.mode
    if mode == RecordingSchedule.Mode.OFF:
        return False
    if mode == RecordingSchedule.Mode.SCHEDULED:
        return within_weekly_window(sched.weekly, now)
    # continuous and motion both keep the stream recording (motion in short
    # segments); off/scheduled handled above.
    return True


def reconcile_recording(camera):
    """Push the effective record state for a camera to MediaMTX. Never raises."""
    return media_client.sync_camera_path(
        camera, record=should_record(camera), segment_seconds=segment_seconds(camera)
    )


def start_recording(camera, user=None):
    """Begin (or reuse) a manual recording session and enable MediaMTX recording."""
    session = active_manual_session(camera)
    if session is None:
        session = ManualRecordingSession.objects.create(camera=camera, started_by=user)
    reconcile_recording(camera)
    return session


def stop_recording(camera, user=None):
    """End any active manual session; recording reverts to the schedule state."""
    ManualRecordingSession.objects.filter(
        camera=camera, status=ManualRecordingSession.Status.RECORDING
    ).update(status=ManualRecordingSession.Status.STOPPED, stopped_at=timezone.now())
    reconcile_recording(camera)


def recording_status(camera):
    """Serializable snapshot of a camera's recording state for the API/UI."""
    sched = _schedule(camera)
    session = active_manual_session(camera)
    return {
        "recording": should_record(camera),
        "mode": sched.mode if sched else RecordingSchedule.Mode.OFF,
        "manual": session is not None,
        "session": (
            {
                "id": session.id,
                "started_at": session.started_at,
                "started_by": getattr(session.started_by, "username", None),
            }
            if session
            else None
        ),
    }
