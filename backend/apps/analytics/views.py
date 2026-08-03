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
    """Per-detector run count, average latency and last-seen (Phase 7 monitoring)."""
    if not request.user.has_vms_perm("analytics.view"):
        return Response({"detail": "عدم دسترسی."}, status=403)
    from .pipeline import detector_health as _health

    return Response(_health())


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
