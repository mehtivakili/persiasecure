from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("analytics-rules", views.AnalyticsRuleViewSet, basename="analyticsrule")
router.register("plate-reads", views.PlateReadViewSet, basename="platereads")
router.register("object-detections", views.ObjectDetectionViewSet, basename="objectdetections")
router.register("plate-watchlist", views.PlateWatchlistViewSet, basename="platewatchlist")

urlpatterns = [
    path("analytics/heatmap", views.motion_heatmap, name="motion-heatmap"),
    path("analytics/detectors/health", views.detector_health, name="detector-health"),
    path(
        "analytics/cameras/<int:camera_id>/detections",
        views.camera_detections,
        name="camera-detections",
    ),
    path("", include(router.urls)),
]
