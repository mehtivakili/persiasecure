import hashlib
import os

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import log_action
from apps.accounts.permissions import HasVmsPermission
from apps.recordings.models import Recording

from .models import CustodyLog, EvidenceCase, EvidenceItem
from .serializers import EvidenceCaseSerializer, EvidenceItemSerializer


def _sha256(path):
    if not path or not os.path.exists(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class EvidenceCaseViewSet(viewsets.ModelViewSet):
    serializer_class = EvidenceCaseSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "evidence.manage"
    required_perm_read = "evidence.view"
    search_fields = ["case_number", "title"]
    filterset_fields = ["status"]

    def get_queryset(self):
        qs = EvidenceCase.objects.prefetch_related("items", "custody")
        if self.request.user.is_superuser:
            return qs
        return qs.filter(organization=self.request.user.organization)

    def perform_create(self, serializer):
        case = serializer.save(
            organization=self.request.user.organization, created_by=self.request.user
        )
        CustodyLog.objects.create(
            case=case, user=self.request.user, action="created", note=case.case_number
        )
        log_action(self.request, "evidence.create", case.case_number)

    @action(detail=True, methods=["post"], url_path="add-recording")
    def add_recording(self, request, pk=None):
        """Attach a recording to the case, hashing the file for integrity."""
        case = self.get_object()
        rec = Recording.objects.filter(id=request.data.get("recording")).first()
        if not rec:
            return Response({"detail": "ضبط یافت نشد."}, status=status.HTTP_404_NOT_FOUND)
        item = EvidenceItem.objects.create(
            case=case,
            kind="recording",
            camera=rec.camera,
            recording=rec,
            file_path=rec.file_path,
            sha256=_sha256(rec.file_path),
            added_by=request.user,
        )
        CustodyLog.objects.create(
            case=case, user=request.user, action="item_added",
            note=f"recording #{rec.id}",
        )
        log_action(request, "evidence.add_recording", case.case_number)
        return Response(EvidenceItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def add_note(self, request, pk=None):
        case = self.get_object()
        item = EvidenceItem.objects.create(
            case=case, kind="note", note=request.data.get("note", ""), added_by=request.user
        )
        CustodyLog.objects.create(case=case, user=request.user, action="note_added")
        return Response(EvidenceItemSerializer(item).data, status=201)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        case = self.get_object()
        case.status = EvidenceCase.Status.CLOSED
        case.save(update_fields=["status"])
        CustodyLog.objects.create(case=case, user=request.user, action="closed")
        log_action(request, "evidence.close", case.case_number)
        return Response(EvidenceCaseSerializer(case).data)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        """Re-hash each item's file and report whether it still matches."""
        case = self.get_object()
        results = []
        for item in case.items.exclude(kind="note"):
            current = _sha256(item.file_path)
            results.append(
                {
                    "item": item.id,
                    "intact": bool(current) and current == item.sha256,
                    "missing": not current,
                }
            )
        return Response({"results": results})
