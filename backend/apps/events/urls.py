from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("events", views.EventViewSet, basename="event")
router.register("bookmarks", views.BookmarkViewSet, basename="bookmark")
router.register("automation-rules", views.AutomationRuleViewSet, basename="automationrule")

urlpatterns = [
    path("settings/notifications", views.notification_settings, name="notification-settings"),
    path("settings/notifications/test", views.notification_test, name="notification-test"),
    path("", include(router.urls)),
]
