from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import log_action
from apps.accounts.permissions import HasVmsPermission

from . import controller
from .models import AccessEvent, AccessRule, Cardholder, Credential, Door
from .serializers import (
    AccessEventSerializer,
    AccessRuleSerializer,
    CardholderSerializer,
    CredentialSerializer,
    DoorSerializer,
)


def _org(request, qs, path="organization"):
    if request.user.is_superuser:
        return qs
    return qs.filter(**{path: request.user.organization})


class DoorViewSet(viewsets.ModelViewSet):
    serializer_class = DoorSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "access.manage"
    required_perm_read = "access.view"
    filterset_fields = ["state"]

    def get_queryset(self):
        return _org(self.request, Door.objects.select_related("camera"))

    def perform_create(self, serializer):
        door = serializer.save(organization=self.request.user.organization)
        log_action(self.request, "door.create", door.name)

    @action(detail=True, methods=["post"])
    def unlock(self, request, pk=None):
        """Momentarily unlock the door (video-verified manual override)."""
        door = self.get_object()
        if not request.user.has_vms_perm("access.manage"):
            return Response({"detail": "عدم دسترسی."}, status=403)
        ok = controller.unlock(door)
        AccessEvent.objects.create(
            organization=door.organization,
            door=door,
            decision="granted",
            reason="بازکردن دستی توسط اپراتور",
        )
        log_action(request, "door.unlock", door.name)
        return Response({"ok": ok})

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        door = self.get_object()
        ok = controller.lock(door)
        return Response({"ok": ok})

    @action(detail=True, methods=["post"])
    def evaluate(self, request, pk=None):
        """
        Decide access for a presented credential at this door.
        Body: {value, kind}. Records an AccessEvent and unlocks if granted.
        Typically called by a reader/controller integration.
        """
        door = self.get_object()
        value = request.data.get("value", "")
        cred = (
            Credential.objects.filter(value=value, active=True, cardholder__active=True)
            .select_related("cardholder")
            .first()
        )
        decision, reason, cardholder = "denied", "اعتبارنامه نامعتبر", None
        if cred:
            cardholder = cred.cardholder
            rule = AccessRule.objects.filter(door=door, cardholder=cardholder).first()
            if rule and rule.allowed:
                decision, reason = "granted", "دسترسی مجاز"
            else:
                reason = "قانون دسترسی وجود ندارد"
        ev = AccessEvent.objects.create(
            organization=door.organization,
            door=door,
            cardholder=cardholder,
            credential_value=value,
            decision=decision,
            reason=reason,
        )
        if decision == "granted":
            controller.unlock(door)
        return Response(AccessEventSerializer(ev).data, status=status.HTTP_201_CREATED)


class CardholderViewSet(viewsets.ModelViewSet):
    serializer_class = CardholderSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "access.manage"
    required_perm_read = "access.view"
    search_fields = ["first_name", "last_name", "employee_id"]

    def get_queryset(self):
        return _org(self.request, Cardholder.objects.prefetch_related("credentials"))

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)


class CredentialViewSet(viewsets.ModelViewSet):
    serializer_class = CredentialSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "access.manage"
    required_perm_read = "access.view"
    filterset_fields = ["cardholder", "kind"]

    def get_queryset(self):
        return _org(self.request, Credential.objects.all(), path="cardholder__organization")


class AccessRuleViewSet(viewsets.ModelViewSet):
    serializer_class = AccessRuleSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "access.manage"
    required_perm_read = "access.view"
    filterset_fields = ["door", "cardholder"]

    def get_queryset(self):
        return _org(self.request, AccessRule.objects.select_related("door", "cardholder"),
                    path="door__organization")


class AccessEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AccessEventSerializer
    permission_classes = [HasVmsPermission]
    required_perm_read = "access.view"
    filterset_fields = ["door", "decision"]
    ordering_fields = ["ts"]

    def get_queryset(self):
        return _org(self.request, AccessEvent.objects.select_related("door", "cardholder"))
