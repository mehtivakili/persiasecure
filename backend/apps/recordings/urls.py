from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("recording-schedules", views.RecordingScheduleViewSet, basename="schedule")
router.register("recordings", views.RecordingViewSet, basename="recording")
router.register("event-clips", views.EventClipViewSet, basename="eventclip")
router.register("exports", views.ExportJobViewSet, basename="export")

urlpatterns = [path("", include(router.urls))]
