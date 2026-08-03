from django.contrib import admin

from .models import (
    EventClip,
    ExportJob,
    ManualRecordingSession,
    Recording,
    RecordingSchedule,
)


@admin.register(EventClip)
class EventClipAdmin(admin.ModelAdmin):
    list_display = ("event", "camera", "status", "start", "end", "duration", "protected_until")
    list_filter = ("status", "camera")


@admin.register(ManualRecordingSession)
class ManualRecordingSessionAdmin(admin.ModelAdmin):
    list_display = ("camera", "status", "started_by", "started_at", "stopped_at")
    list_filter = ("status",)


@admin.register(RecordingSchedule)
class RecordingScheduleAdmin(admin.ModelAdmin):
    list_display = ("camera", "mode", "retention_days", "segment_seconds")
    list_filter = ("mode",)


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ("camera", "start", "end", "duration", "size", "status", "has_motion")
    list_filter = ("camera", "status", "has_motion")
    date_hierarchy = "start"


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ("camera", "start", "end", "status", "requested_by", "created_at")
    list_filter = ("status",)
