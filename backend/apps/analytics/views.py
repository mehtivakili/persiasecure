from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.permissions import HasVmsPermission

from .models import AnalyticsRule, ObjectDetection, PlateRead, PlateWatchlist
from .serializers import (
    AnalyticsRuleSerializer,
    ObjectDetectionSerializer,
    PlateReadSerializer,
    PlateWatchlistSerializer,
)


def _org(request, qs):
    if request.user.is_superuser:
        return qs
    return qs.filter(organization=request.user.organization)


@api_view(["GET"])
@permission_classes([HasVmsPermission])
def detector_health(request):
    """
    Per-detector run count, average latency and last-seen (Phase 7 monitoring),
    plus a best-effort GPU/CPU hardware snapshot and the active model registry
    (Phase AI-0). Lets an operator see, at a glance, which model is live on which
    device and whether the inference host is keeping up.
    """
    if not request.user.has_vms_perm("analytics.view"):
        return Response({"detail": "عدم دسترسی."}, status=403)
    from .inference import registry
    from .models import DetectorModel
    from .pipeline import detector_health as _health

    active = [
        {
            "task": m.task,
            "name": m.name,
            "version": m.version,
            "framework": m.framework,
            "device": m.device,
        }
        for m in DetectorModel.objects.filter(active=True)
    ]
    return Response({
        "detectors": _health(),
        "hardware": registry.hardware_snapshot(),
        "active_models": active,
    })


@api_view(["GET"])
@permission_classes([HasVmsPermission])
def camera_detections(request, camera_id):
    """
    Latest object detections for one camera, for the live-view overlay:
      { active, model, age_seconds, detections:[{label,confidence,bbox,track_id}] }
    `active` = an enabled object rule exists on the camera; `detections` are the
    boxes from the most recent frame the detector ran (normalized 0..1).
    """
    if not request.user.has_vms_perm("analytics.view"):
        return Response({"detail": "عدم دسترسی."}, status=403)
    from apps.cameras.models import Camera

    from .inference import overlay

    cams = Camera.objects.filter(id=camera_id)
    if not request.user.is_superuser:
        cams = cams.filter(organization=request.user.organization)
    camera = cams.first()
    if camera is None:
        return Response({"detail": "دوربین یافت نشد."}, status=404)

    active = AnalyticsRule.objects.filter(camera=camera, kind="object", enabled=True).exists()
    data = overlay.latest(camera_id)
    age = None
    detections = []
    model = ""
    if data:
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone as _tz

        ts = parse_datetime(data.get("ts", ""))
        if ts:
            age = round((_tz.now() - ts).total_seconds(), 1)
        detections = data.get("detections", [])
        model = data.get("model", "")
    return Response({"active": active, "model": model, "age_seconds": age, "detections": detections})


class AnalyticsRuleViewSet(viewsets.ModelViewSet):
    serializer_class = AnalyticsRuleSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "analytics.manage"
    required_perm_read = "analytics.view"
    filterset_fields = ["camera", "kind", "enabled"]

    def get_queryset(self):
        return _org(self.request, AnalyticsRule.objects.select_related("camera"))

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)

    @action(detail=True, methods=["post"])
    def run_now(self, request, pk=None):
        """Trigger this rule's worker immediately (for testing)."""
        from . import tasks

        rule = self.get_object()
        if rule.kind == "alpr":
            tasks.alpr_worker.delay(rule.id)
        elif rule.kind == "object":
            tasks.object_worker.delay(rule.id)
        elif rule.kind == "fire":
            tasks.fire_worker.delay(rule.id)
        elif rule.kind == "smoke":
            tasks.smoke_worker.delay(rule.id)
        elif rule.kind == "tripwire":
            tasks.tripwire_worker.delay(rule.id)
        else:
            tasks.motion_worker.delay(rule.camera_id)
        return Response({"queued": True})


class PlateReadViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PlateReadSerializer
    permission_classes = [HasVmsPermission]
    required_perm_read = "analytics.view"
    filterset_fields = ["camera", "watchlist_hit"]
    search_fields = ["plate"]
    ordering_fields = ["ts", "confidence"]

    def get_queryset(self):
        return _org(self.request, PlateRead.objects.select_related("camera"))


class ObjectDetectionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ObjectDetectionSerializer
    permission_classes = [HasVmsPermission]
    required_perm_read = "analytics.view"
    filterset_fields = ["camera", "label"]
    ordering_fields = ["ts", "confidence"]

    def get_queryset(self):
        return _org(self.request, ObjectDetection.objects.select_related("camera"))


@api_view(["GET"])
@permission_classes([HasVmsPermission])
def motion_heatmap(request):
    """Summed motion heatmap grid for ?camera=<id>&days=<n> (default 7)."""
    from apps.cameras.models import Camera

    from . import heatmap as hm

    if not request.user.has_vms_perm("analytics.view"):
        return Response({"detail": "عدم دسترسی."}, status=403)
    cam_qs = Camera.objects.all()
    if not request.user.is_superuser:
        cam_qs = cam_qs.filter(organization=request.user.organization)
    camera = cam_qs.filter(id=request.query_params.get("camera")).first()
    if not camera:
        return Response({"detail": "دوربین یافت نشد."}, status=404)
    days = min(int(request.query_params.get("days", 7)), 90)
    return Response(hm.summarize(camera, days=days))


class PlateWatchlistViewSet(viewsets.ModelViewSet):
    serializer_class = PlateWatchlistSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "analytics.manage"
    required_perm_read = "analytics.view"
    search_fields = ["plate"]

    def get_queryset(self):
        return _org(self.request, PlateWatchlist.objects.all())

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)
