from urllib.parse import quote

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from apps.accounts.models import log_action
from apps.accounts.permissions import HasVmsPermission, OrgScopedQuerysetMixin
from apps.mediactl import client as media_client
from apps.mediactl import ffmpeg

from . import onvif
from .models import Camera, CameraGroup, PtzPreset
from .serializers import CameraGroupSerializer, CameraSerializer, PtzPresetSerializer


class MediaConfigError(APIException):
    """Raised when MediaMTX cannot be configured for a camera path."""

    status_code = 503
    default_detail = (
        "پیکربندی سرور رسانه ناموفق بود. از روشن‌بودن MediaMTX و صحت اطلاعات "
        "اتصال دوربین مطمئن شوید."
    )
    default_code = "mediamtx_failure"


class CameraViewSet(OrgScopedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = CameraSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "camera.manage"
    required_perm_read = "camera.view"
    queryset = (
        Camera.objects.all()
        .select_related("schedule")
        .prefetch_related("stream_profiles", "ptz_presets")
    )
    search_fields = ["name", "location", "manufacturer", "model"]
    filterset_fields = ["status", "enabled"]

    def perform_create(self, serializer):
        # Create the camera + stream profiles + recording schedule and configure
        # MediaMTX as one unit. If the media server cannot be configured, the
        # transaction rolls the database back and any partial MediaMTX path is
        # removed — the camera is never left half‑onboarded (Phase 1).
        from apps.recordings import services

        with transaction.atomic():
            camera = serializer.save()
            if not services.reconcile_recording(camera):
                media_client.remove_camera_path(camera)
                raise MediaConfigError()
            log_action(self.request, "camera.create", camera.name)

    def perform_update(self, serializer):
        from apps.recordings import services

        with transaction.atomic():
            camera = serializer.save()
            if not services.reconcile_recording(camera):
                raise MediaConfigError()
            log_action(self.request, "camera.update", camera.name)

    def perform_destroy(self, instance):
        media_client.remove_camera_path(instance)
        log_action(self.request, "camera.delete", instance.name)
        instance.delete()

    @action(detail=True, methods=["post"], url_path="recording/start")
    def recording_start(self, request, pk=None):
        """Start an operator-controlled recording session (Phase 2)."""
        from apps.recordings import services

        camera = self.get_object()
        services.start_recording(camera, request.user)
        log_action(request, "recording.start", camera.name)
        return Response(services.recording_status(camera))

    @action(detail=True, methods=["post"], url_path="recording/stop")
    def recording_stop(self, request, pk=None):
        """Stop the manual recording session; recording reverts to the schedule."""
        from apps.recordings import services

        camera = self.get_object()
        services.stop_recording(camera, request.user)
        log_action(request, "recording.stop", camera.name)
        return Response(services.recording_status(camera))

    @action(detail=True, methods=["get"], url_path="recording/status")
    def recording_status(self, request, pk=None):
        """Current effective recording state (schedule + manual)."""
        from apps.recordings import services

        camera = self.get_object()
        return Response(services.recording_status(camera))

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """Structured connectivity probe for a saved camera (uses stored creds)."""
        camera = self.get_object()
        url = media_client.build_source_url(camera)
        result = ffmpeg.probe_source(url)
        result["source"] = _mask(url)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="test-connection")
    def test_connection(self, request):
        """
        Structured connectivity probe from raw connection parameters — used by
        the onboarding wizard BEFORE the camera is saved. Optionally accepts a
        `camera` id (validated against the caller's organization) to reuse the
        stored password when editing, so the password is never resent by the
        browser.
        """
        if not request.user.has_vms_perm("camera.manage"):
            return Response({"detail": "عدم دسترسی."}, status=403)
        data = request.data
        params = {k: data.get(k) for k in (
            "protocol", "host", "port", "path", "rtsp_url", "username", "password",
        )}
        transport = data.get("rtsp_transport", "tcp")

        cam_id = data.get("camera")
        if cam_id:
            qs = Camera.objects.all()
            if not request.user.is_superuser:
                qs = qs.filter(organization=request.user.organization)
            camera = qs.filter(id=cam_id).first()
            if camera is None:
                return Response(
                    {"detail": "دوربین متعلق به سازمان شما نیست.", "reason": "forbidden"},
                    status=404,
                )
            # Editing without re-entering the password: fall back to stored creds.
            if not params.get("password"):
                params["password"] = camera.password
            if not params.get("host") and not params.get("rtsp_url"):
                url = media_client.build_source_url(camera)
                result = ffmpeg.probe_source(url, transport=transport)
                result["source"] = _mask(url)
                return Response(result)

        url = _build_url_from_params(params)
        if not url:
            return Response(
                {"reachable": False, "reason": "invalid", "detail": "اطلاعات اتصال ناقص است."},
                status=400,
            )
        result = ffmpeg.probe_source(url, transport=transport)
        result["source"] = _mask(url)
        return Response(result)

    @action(detail=True, methods=["get"])
    def snapshot(self, request, pk=None):
        """Return a fresh JPEG snapshot from the camera."""
        camera = self.get_object()
        url = media_client.build_source_url(camera)
        data = ffmpeg.grab_snapshot(url)
        if not data:
            return Response(
                {"detail": "دریافت تصویر ناموفق بود."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        from django.http import HttpResponse

        return HttpResponse(data, content_type="image/jpeg")

    @action(detail=True, methods=["post"])
    def ptz(self, request, pk=None):
        """
        PTZ control. Body: {action: move|stop|preset, pan, tilt, zoom, token}.
        Requires ptz.control permission.
        """
        camera = self.get_object()
        if not request.user.has_vms_perm("ptz.control"):
            return Response({"detail": "عدم دسترسی PTZ."}, status=403)
        act = request.data.get("action", "move")
        if act == "stop":
            ok = onvif.ptz_stop(camera)
        elif act == "preset":
            ok = onvif.ptz_goto_preset(camera, request.data.get("token", ""))
        else:
            ok = onvif.ptz_move(
                camera,
                pan=float(request.data.get("pan", 0)),
                tilt=float(request.data.get("tilt", 0)),
                zoom=float(request.data.get("zoom", 0)),
            )
        return Response({"ok": ok})

    @action(detail=True, methods=["get", "post"], url_path="ptz-presets")
    def ptz_presets(self, request, pk=None):
        camera = self.get_object()
        if request.method == "POST":
            ser = PtzPresetSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save(camera=camera)
            return Response(ser.data, status=201)
        return Response(PtzPresetSerializer(camera.ptz_presets.all(), many=True).data)


@api_view(["GET"])
@permission_classes([HasVmsPermission])
def camera_brands(request):
    """
    Catalog of supported CCTV brands with their RTSP path templates.
    Any RTSP/ONVIF camera works; these are convenience presets.
    """
    from .presets import CAMERA_BRANDS

    return Response(CAMERA_BRANDS)


@api_view(["POST"])
@permission_classes([HasVmsPermission])
def onvif_discover(request):
    """Scan the local network for ONVIF devices."""
    if not request.user.has_vms_perm("camera.manage"):
        return Response({"detail": "عدم دسترسی."}, status=403)
    devices = onvif.discover(timeout=int(request.data.get("timeout", 4)))
    return Response({"devices": devices})


@api_view(["POST"])
@permission_classes([HasVmsPermission])
def onvif_probe(request):
    """Given host/port/creds, fetch device info + RTSP URI via ONVIF."""
    if not request.user.has_vms_perm("camera.manage"):
        return Response({"detail": "عدم دسترسی."}, status=403)
    host = request.data.get("host")
    port = int(request.data.get("port", 80))
    user = request.data.get("username", "")
    pwd = request.data.get("password", "")
    info = onvif.get_device_info(host, port, user, pwd)
    uri = onvif.get_stream_uri(host, port, user, pwd)
    return Response({"info": info, "rtsp_url": uri})


class CameraGroupViewSet(OrgScopedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = CameraGroupSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "camera.manage"
    required_perm_read = "camera.view"
    queryset = CameraGroup.objects.all().prefetch_related("cameras")


def _build_url_from_params(d):
    """
    Build an RTSP URL from raw connection parameters (wizard test step). Mirrors
    media_client.build_source_url: structured host/port/path win over a full URL.
    """
    rtsp_url = (d.get("rtsp_url") or "").strip()
    host = (d.get("host") or "").strip()
    if host:
        auth = ""
        if d.get("username"):
            user = quote(str(d.get("username")), safe="")
            password = quote(str(d.get("password") or ""), safe="")
            auth = f"{user}:{password}@"
        protocol = d.get("protocol") or "rtsp"
        port = d.get("port") or 554
        path = d.get("path") or "/"
        return f"{protocol}://{auth}{host}:{port}{path}"
    return rtsp_url


def _mask(url):
    """Hide credentials in an RTSP URL for display."""
    if url and "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return url
