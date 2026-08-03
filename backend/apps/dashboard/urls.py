from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import desk, health, reports, views

router = DefaultRouter()
router.register("desk-layouts", desk.DeskLayoutViewSet, basename="desklayout")

urlpatterns = [
    path("dashboard/summary", views.summary, name="dashboard-summary"),
    path("dashboard/events-timeseries", views.events_timeseries, name="dashboard-events-ts"),
    path("reports/<str:kind>", reports.report, name="report-csv"),
    path("system/health", health.system_health, name="system-health"),
    path("", include(router.urls)),
]
