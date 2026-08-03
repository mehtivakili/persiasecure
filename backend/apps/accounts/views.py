from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import PERMISSION_CHOICES, AuditLog, Role, User, log_action
from .permissions import HasVmsPermission
from .serializers import (
    AuditLogSerializer,
    MeSerializer,
    PersianTokenObtainPairSerializer,
    RoleSerializer,
    UserSerializer,
)


class PersianTokenObtainPairView(TokenObtainPairView):
    serializer_class = PersianTokenObtainPairSerializer
    # Rate-limit login attempts to blunt credential stuffing / brute force.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """Return the current user's profile + permissions."""
    return Response(MeSerializer(request.user).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def permission_catalog(request):
    """All permission codenames + Persian labels for the RBAC editor."""
    return Response([{"code": c, "label": str(l)} for c, l in PERMISSION_CHOICES])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_threat_level(request):
    """
    Genetec-style threat level switch for the whole organization.
    Body: {level: green|yellow|red}. Requires threat.manage.
    """
    from .models import THREAT_LEVELS

    if not request.user.has_vms_perm("threat.manage"):
        return Response({"detail": "عدم دسترسی."}, status=403)
    level = request.data.get("level")
    if level not in dict(THREAT_LEVELS):
        return Response({"detail": "سطح تهدید نامعتبر است."}, status=400)
    org = request.user.organization
    if org is None:
        return Response({"detail": "سازمانی برای کاربر ثبت نشده است."}, status=400)
    org.threat_level = level
    org.save(update_fields=["threat_level"])
    log_action(request, "threat.set", level)
    # Surface the change in the alarm feed so all operators see it live.
    from apps.events.models import Event
    from apps.events.utils import broadcast_event

    ev = Event.objects.create(
        organization=org,
        type="manual",
        severity="critical" if level == "red" else ("warning" if level == "yellow" else "info"),
        details={"message": f"سطح تهدید به «{dict(THREAT_LEVELS)[level]}» تغییر کرد.", "threat_level": level},
    )
    broadcast_event(ev)
    return Response({"threat_level": level})


class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "user.manage"
    required_perm_read = "user.manage"

    def get_queryset(self):
        user = self.request.user
        qs = Role.objects.all()
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs.order_by("name")

    def perform_create(self, serializer):
        org = self.request.user.organization
        role = serializer.save(organization=org)
        log_action(self.request, "role.create", role.name)

    def perform_update(self, serializer):
        role = serializer.save()
        log_action(self.request, "role.update", role.name)

    def perform_destroy(self, instance):
        log_action(self.request, "role.delete", instance.name)
        instance.delete()


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "user.manage"
    required_perm_read = "user.manage"
    search_fields = ["username", "email", "display_name"]

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.select_related("role", "organization")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs.order_by("username")

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request, "user.create", obj.username)

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request, "user.update", obj.username)

    def perform_destroy(self, instance):
        log_action(self.request, "user.delete", instance.username)
        instance.delete()


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [HasVmsPermission]
    required_perm_read = "user.manage"
    filterset_fields = ["action", "user"]

    def get_queryset(self):
        user = self.request.user
        qs = AuditLog.objects.select_related("user")
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs
