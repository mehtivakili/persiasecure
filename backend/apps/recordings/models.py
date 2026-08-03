"""
Recording schedules and the clip index.

RecordingSchedule mirrors Shinobi's record modes (continuous / motion /
scheduled / off) plus retention and segment length. Recording rows are the
index of mp4/fmp4 segments written by MediaMTX to the shared volume; the
`index_recordings` Celery task scans the volume and creates them.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.cameras.models import Camera


class RecordingSchedule(models.Model):
    class Mode(models.TextChoices):
        OFF = "off", _("خاموش")
        CONTINUOUS = "continuous", _("پیوسته")
        MOTION = "motion", _("مبتنی بر حرکت")
        SCHEDULED = "scheduled", _("زمان‌بندی‌شده")

    camera = models.OneToOneField(
        Camera, on_delete=models.CASCADE, related_name="schedule"
    )
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.OFF)
    # weekly[<0-6>] = list of {"from": "HH:MM", "to": "HH:MM"} for scheduled mode
    weekly = models.JSONField(default=dict, blank=True)
    retention_days = models.PositiveIntegerField(_("نگهداری (روز)"), default=14)
    segment_seconds = models.PositiveIntegerField(default=60)
    pre_event_seconds = models.PositiveIntegerField(default=5)
    post_event_seconds = models.PositiveIntegerField(default=10)

    class Meta:
        verbose_name = _("زمان‌بندی ضبط")
        verbose_name_plural = _("زمان‌بندی‌های ضبط")
        ordering = ("camera_id",)

    def __str__(self):
        return f"{self.camera.name}: {self.get_mode_display()}"


class ManualRecordingSession(models.Model):
    """
    An operator-initiated recording session, independent of the weekly schedule.
    While a session is `recording`, the camera records even if its schedule mode
    is `off`; stopping the session reverts to the schedule-driven state. This is
    what powers the live Start/Stop recording button (Phase 2, missing item #5).
    """

    class Status(models.TextChoices):
        RECORDING = "recording", _("در حال ضبط")
        STOPPED = "stopped", _("متوقف‌شده")

    camera = models.ForeignKey(
        Camera, on_delete=models.CASCADE, related_name="manual_sessions"
    )
    started_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.RECORDING, db_index=True
    )

    class Meta:
        verbose_name = _("ضبط دستی")
        verbose_name_plural = _("ضبط‌های دستی")
        ordering = ("-started_at",)
        indexes = [models.Index(fields=["camera", "status"])]

    def __str__(self):
        return f"{self.camera.name} manual @ {self.started_at:%Y-%m-%d %H:%M}"


class Recording(models.Model):
    class Status(models.IntegerChoices):
        BUILDING = 0, _("در حال ضبط")
        COMPLETE = 1, _("کامل")
        ARCHIVED = 3, _("بایگانی")

    camera = models.ForeignKey(
        Camera, on_delete=models.CASCADE, related_name="recordings"
    )
    start = models.DateTimeField(db_index=True)
    end = models.DateTimeField(null=True, blank=True)
    file_path = models.CharField(max_length=500, unique=True)
    size = models.BigIntegerField(default=0)  # bytes
    duration = models.FloatField(default=0)  # seconds
    status = models.IntegerField(choices=Status.choices, default=Status.COMPLETE)
    has_motion = models.BooleanField(default=False)
    # Protected segments (evidence / legal hold) are never pruned by retention.
    protected = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("ضبط")
        verbose_name_plural = _("ضبط‌ها")
        ordering = ("-start",)
        indexes = [models.Index(fields=["camera", "start"])]

    def __str__(self):
        return f"{self.camera.name} @ {self.start:%Y-%m-%d %H:%M}"


class ExportJob(models.Model):
    """Evidence export request (clip cut from recordings)."""

    class Status(models.TextChoices):
        PENDING = "pending", _("در صف")
        RUNNING = "running", _("در حال پردازش")
        DONE = "done", _("آماده")
        FAILED = "failed", _("ناموفق")

    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="exports")
    requested_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    output_file = models.CharField(max_length=500, blank=True, default="")
    size = models.BigIntegerField(default=0)  # bytes
    sha256 = models.CharField(max_length=64, blank=True, default="")  # evidence integrity
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Export {self.camera.name} {self.start:%Y-%m-%d %H:%M}"


class EventClip(models.Model):
    """
    A short MP4 assembled around an Event from the rolling recording buffer:
    video from `event - pre_event` to `event + post_event`. Produced
    asynchronously by apps.recordings.tasks.assemble_event_clip (Phase 3).
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("در صف")
        ASSEMBLING = "assembling", _("در حال آماده‌سازی")
        READY = "ready", _("آماده")
        FAILED = "failed", _("ناموفق")

    event = models.OneToOneField(
        "events.Event", on_delete=models.CASCADE, related_name="clip"
    )
    camera = models.ForeignKey(
        Camera, on_delete=models.CASCADE, related_name="event_clips"
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    file_path = models.CharField(max_length=500, blank=True, default="")
    size = models.BigIntegerField(default=0)  # bytes
    duration = models.FloatField(default=0)  # seconds
    sha256 = models.CharField(max_length=64, blank=True, default="")
    error = models.CharField(max_length=255, blank=True, default="")
    # Legal hold: while set in the future, the clip is retained regardless of age.
    protected_until = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("کلیپ رویداد")
        verbose_name_plural = _("کلیپ‌های رویداد")
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["camera", "start"])]

    def __str__(self):
        return f"Clip evt#{self.event_id} [{self.status}]"
