import os

from django.db.models import Q
from django.http import Http404
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.models import log_action
from apps.accounts.permissions import HasVmsPermission
from apps.mediactl import client as media_client

from .models import EventClip, ExportJob, Recording, RecordingSchedule
from .playback import ranged_file_response, signed_stream_url, verify_recording_sig
from .serializers import (
    EventClipSerializer,
    ExportJobSerializer,
    RecordingScheduleSerializer,
    RecordingSerializer,
)


def _org_filter(request, qs, camera_path="camera__organization"):
    if request.user.is_superuser:
        return qs
    return qs.filter(**{camera_path: request.user.organization})


class RecordingScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = RecordingScheduleSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "camera.manage"
    required_perm_read = "camera.view"
    filterset_fields = ["camera", "mode"]

    def get_queryset(self):
        return _org_filter(self.request, RecordingSchedule.objects.select_related("camera"))

    def perform_update(self, serializer):
        from . import services

        sched = serializer.save()
        # Reconcile MediaMTX with the effective record state (schedule + manual).
        services.reconcile_recording(sched.camera)
        log_action(self.request, "schedule.update", sched.camera.name, mode=sched.mode)

    def perform_create(self, serializer):
        from . import services

        sched = serializer.save()
        services.reconcile_recording(sched.camera)


class RecordingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RecordingSerializer
    permission_classes = [HasVmsPermission]
    required_perm_read = "playback.view"
    filterset_fields = ["camera", "has_motion", "status"]
    ordering_fields = ["start", "duration"]

    def get_queryset(self):
        qs = _org_filter(self.request, Recording.objects.select_related("camera"))
        # Time-range filtering for the playback timeline.
        params = self.request.query_params
        after = params.get("after")
        before = params.get("before")
        if after and (dt := parse_datetime(after)):
            qs = qs.filter(start__gte=dt)
        if before and (dt := parse_datetime(before)):
            qs = qs.filter(start__lte=dt)
        return qs

    @action(detail=False, methods=["get"])
    def timeline(self, request):
        """
        Chronological segments overlapping a camera + time window, WITHOUT DRF
        pagination, so the playback page shows a whole day (issue #6). Uses
        *overlap* filtering (a segment that starts before the window but runs
        into it is included) and returns a short-lived *signed* stream URL per
        segment so <video> can play/seek it with native HTTP Range (issue #8).
        """
        qs = _org_filter(request, Recording.objects.select_related("camera"))
        params = request.query_params
        if camera := params.get("camera"):
            qs = qs.filter(camera_id=camera)
        after = parse_datetime(params.get("after") or "")
        before = parse_datetime(params.get("before") or "")
        if before:
            qs = qs.filter(start__lt=before)
        if after:
            # end may be null while a segment is still being written.
            qs = qs.filter(Q(end__gt=after) | Q(end__isnull=True))
        qs = qs.order_by("start")[:5000]
        data = [
            {
                "id": r.id,
                "start": r.start,
                "end": r.end,
                "duration": r.duration,
                "size": r.size,
                "has_motion": r.has_motion,
                "stream_url": signed_stream_url(r.id),
            }
            for r in qs
        ]
        return Response(data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def stream(self, request, pk=None):
        """
        Stream a recording segment with proper HTTP Range support. Authorized by
        a signed `sig` token (minted by the org-scoped timeline) so a plain
        <video src> works, or by an authenticated user with playback.view.
        """
        rec = None
        if verify_recording_sig(request.query_params.get("sig"), pk):
            rec = Recording.objects.filter(pk=pk).first()
        else:
            user = request.user
            if user and user.is_authenticated and (
                user.is_superuser or user.has_vms_perm("playback.view")
            ):
                scoped = Recording.objects.all()
                if not user.is_superuser:
                    scoped = scoped.filter(camera__organization=user.organization)
                rec = scoped.filter(pk=pk).first()
        if rec is None:
            raise Http404("فایل ضبط یافت نشد.")
        return ranged_file_response(request, rec.file_path, "video/mp4")


class EventClipViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EventClipSerializer
    permission_classes = [HasVmsPermission]
    required_perm_read = "playback.view"
    required_perm = "playback.export"
    filterset_fields = ["camera", "status", "event"]
    ordering_fields = ["created_at", "start"]

    def get_queryset(self):
        return _org_filter(
            self.request, EventClip.objects.select_related("camera", "event")
        )

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        """Re-queue a failed clip for assembly."""
        clip = self.get_object()
        if clip.status != EventClip.Status.FAILED:
            return Response(
                {"detail": "فقط کلیپ‌های ناموفق قابل تلاش مجدد هستند."}, status=400
            )
        clip.status = EventClip.Status.PENDING
        clip.error = ""
        clip.save(update_fields=["status", "error"])
        from .tasks import assemble_event_clip

        assemble_event_clip.delay(clip.id)
        log_action(request, "clip.retry", clip.event_id)
        return Response(EventClipSerializer(clip).data)

    @action(detail=True, methods=["post"])
    def protect(self, request, pk=None):
        """Set/clear a legal-hold date so retention keeps this clip."""
        from django.utils.dateparse import parse_datetime

        clip = self.get_object()
        until = request.data.get("protected_until")
        clip.protected_until = parse_datetime(until) if until else None
        clip.save(update_fields=["protected_until"])
        log_action(request, "clip.protect", clip.event_id)
        return Response(EventClipSerializer(clip).data)

    @action(detail=True, methods=["get"])
    def stream(self, request, pk=None):
        """Stream the assembled clip file with Range support (audited)."""
        clip = self.get_object()
        if clip.status != EventClip.Status.READY or not os.path.exists(clip.file_path):
            raise Http404("کلیپ آماده نیست.")
        log_action(request, "clip.view", clip.event_id)
        return ranged_file_response(request, clip.file_path, "video/mp4")


class ExportJobViewSet(viewsets.ModelViewSet):
    serializer_class = ExportJobSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "playback.export"
    required_perm_read = "playback.view"

    def get_queryset(self):
        return _org_filter(self.request, ExportJob.objects.select_related("camera"))

    def perform_create(self, serializer):
        from .tasks import build_export

        job = serializer.save(requested_by=self.request.user, status=ExportJob.Status.PENDING)
        build_export.delay(job.id)
        log_action(self.request, "recording.export", job.camera.name)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Authenticated, audited download of a finished export (Range‑capable)."""
        job = self.get_object()
        if job.status != ExportJob.Status.DONE or not os.path.exists(job.output_file):
            raise Http404("خروجی آماده نیست.")
        log_action(request, "recording.export.download", job.camera.name)
        resp = ranged_file_response(request, job.output_file, "video/mp4")
        resp["Content-Disposition"] = f'attachment; filename="export_{job.id}.mp4"'
        return resp
