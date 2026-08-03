from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("roles", views.RoleViewSet, basename="role")
router.register("users", views.UserViewSet, basename="user")
router.register("audit-logs", views.AuditLogViewSet, basename="auditlog")

urlpatterns = [
    path("auth/me", views.me, name="me"),
    path("auth/permissions", views.permission_catalog, name="permission-catalog"),
    path("org/threat-level", views.set_threat_level, name="set-threat-level"),
    path("", include(router.urls)),
]
