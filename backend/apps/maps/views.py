from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.accounts.permissions import HasVmsPermission

from .models import MapMarker, SiteMap
from .serializers import MapMarkerSerializer, SiteMapSerializer


class SiteMapViewSet(viewsets.ModelViewSet):
    serializer_class = SiteMapSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "map.manage"
    required_perm_read = "map.view"
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = SiteMap.objects.prefetch_related("markers")
        if self.request.user.is_superuser:
            return qs
        return qs.filter(organization=self.request.user.organization)

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)


class MapMarkerViewSet(viewsets.ModelViewSet):
    serializer_class = MapMarkerSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "map.manage"
    required_perm_read = "map.view"
    filterset_fields = ["site_map", "kind"]

    def get_queryset(self):
        qs = MapMarker.objects.select_related("site_map")
        if self.request.user.is_superuser:
            return qs
        return qs.filter(site_map__organization=self.request.user.organization)
