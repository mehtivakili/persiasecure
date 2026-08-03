from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import log_action
from apps.accounts.permissions import HasVmsPermission

from .models import FederatedServer
from .serializers import FederatedServerSerializer
from .tasks import sync_server


class FederatedServerViewSet(viewsets.ModelViewSet):
    serializer_class = FederatedServerSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "federation.manage"
    required_perm_read = "federation.manage"

    def get_queryset(self):
        qs = FederatedServer.objects.prefetch_related("remote_cameras")
        if self.request.user.is_superuser:
            return qs
        return qs.filter(organization=self.request.user.organization)

    def perform_create(self, serializer):
        server = serializer.save(organization=self.request.user.organization)
        log_action(self.request, "federation.add", server.name)
        sync_server.delay(server.id)

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        """Force an immediate sync of this server's cameras."""
        server = self.get_object()
        sync_server.delay(server.id)
        return Response({"queued": True})
