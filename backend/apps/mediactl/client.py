"""
Thin client for the MediaMTX control API (v3).

Django owns the source of truth (Camera rows). When a camera is created,
enabled, updated or deleted we push a matching "path" into MediaMTX so it
pulls the camera's RTSP feed and re-publishes it as WebRTC/HLS, optionally
recording segments to the shared volume.

Docs: MediaMTX exposes /v3/config/paths/{add,patch,delete}/<name> and
/v3/paths/get/<name> for runtime status.
"""
import logging
import re
from urllib.parse import quote

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 5


def _api(path):
    base = settings.MEDIAMTX["API_URL"].rstrip("/")
    return f"{base}{path}"


def path_name_for(camera):
    """Stable, URL-safe MediaMTX path name for a camera (e.g. 'cam_12')."""
    return f"cam_{camera.id}"


def build_source_url(camera):
    """
    Build the upstream RTSP URL MediaMTX should pull from.
    Structured connection fields are authoritative when a host is present.
    This prevents a stale full URL (often containing an old password or IP)
    from silently overriding the separately entered connection fields.
    """
    if camera.host:
        auth = ""
        if camera.username:
            user = quote(str(camera.username), safe="")
            password = quote(str(camera.password), safe="")
            auth = f"{user}:{password}@"
        protocol = camera.protocol or "rtsp"
        path = camera.path or "/"
        return f"{protocol}://{auth}{camera.host}:{camera.port}{path}"
    if camera.rtsp_url:
        return camera.rtsp_url
    return f"rtsp://{camera.host}:{camera.port}{camera.path or '/'}"


def main_codec(camera):
    """Codec of the camera's main stream profile ('h264' | 'h265')."""
    codec = (
        camera.stream_profiles.filter(kind="main")
        .values_list("codec", flat=True)
        .first()
        or "h264"
    ).lower()
    return "h265" if codec in ("h265", "hevc") else "h264"


def is_hevc(camera):
    return main_codec(camera) == "h265"


def web_path_name_for(camera):
    """
    Path the browser should view. H.264 is viewed directly; H.265/HEVC is
    served through a derived, transcoded H.264 path (browsers can't decode
    HEVC over WebRTC), while the native path keeps recording HEVC.
    """
    name = path_name_for(camera)
    return f"{name}_web" if is_hevc(camera) else name


def _web_transcode_payload(camera):
    """
    MediaMTX path config that, ON DEMAND (only while someone is watching),
    launches ffmpeg to transcode the native HEVC path to H.264 for the browser.
    Requires the mediamtx '-ffmpeg' image. Auto-stops ~15s after the last viewer.
    """
    src = path_name_for(camera)
    web = f"{src}_web"
    cmd = (
        "ffmpeg -nostdin -rtsp_transport tcp "
        f"-i rtsp://localhost:8554/{src} "
        "-c:v libx264 -preset veryfast -tune zerolatency -profile:v high "
        "-pix_fmt yuv420p -g 50 -an "
        f"-f rtsp -rtsp_transport tcp rtsp://localhost:8554/{web}"
    )
    return {
        "runOnDemand": cmd,
        "runOnDemandRestart": True,
        "runOnDemandStartTimeout": "12s",
        "runOnDemandCloseAfter": "15s",
    }


def sync_camera_path(camera, record=False, segment_seconds=60):
    """
    Create or update the MediaMTX path for a camera. Returns True on success.
    Never raises — logs and returns False so a media-server outage doesn't
    break the API.
    """
    name = path_name_for(camera)
    payload = {
        "source": build_source_url(camera),
        # Continuous/motion recording needs the stream pulled at all times
        # (MediaMTX's recorder is not a "reader" that triggers on-demand);
        # without recording, pull on demand to save camera bandwidth.
        "sourceOnDemand": not record,
        "rtspTransport": camera.stream_profiles.filter(kind="main")
        .values_list("rtsp_transport", flat=True)
        .first()
        or "tcp",
    }
    if record:
        payload.update(
            {
                "record": True,
                # MediaMTX requires the %path variable in recordPath; it expands
                # to the path name (e.g. cam_1), matching what the recordings
                # indexer scans for under /recordings/.
                "recordPath": "/recordings/%path/%Y-%m-%d_%H-%M-%S-%f",
                "recordFormat": "fmp4",
                "recordSegmentDuration": f"{segment_seconds}s",
            }
        )
    else:
        payload["record"] = False

    if not camera.enabled:
        return remove_camera_path(camera)

    try:
        # Try patch first (path may already exist), fall back to add.
        r = requests.patch(_api(f"/v3/config/paths/patch/{name}"), json=payload, timeout=TIMEOUT)
        if r.status_code == 404:
            r = requests.post(_api(f"/v3/config/paths/add/{name}"), json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        _sync_web_path(camera)
        return True
    except requests.RequestException as exc:
        logger.warning("MediaMTX sync failed for %s: %s", name, exc)
        return False


def _sync_web_path(camera):
    """Create the on-demand H.264 transcode path for HEVC cameras; else drop it."""
    web = f"{path_name_for(camera)}_web"
    try:
        if is_hevc(camera) and camera.enabled:
            payload = _web_transcode_payload(camera)
            r = requests.patch(_api(f"/v3/config/paths/patch/{web}"), json=payload, timeout=TIMEOUT)
            if r.status_code == 404:
                requests.post(_api(f"/v3/config/paths/add/{web}"), json=payload, timeout=TIMEOUT)
        else:
            requests.delete(_api(f"/v3/config/paths/delete/{web}"), timeout=TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("MediaMTX web-path sync failed for %s: %s", web, exc)


def remove_camera_path(camera):
    name = path_name_for(camera)
    ok = True
    for p in (name, f"{name}_web"):
        try:
            r = requests.delete(_api(f"/v3/config/paths/delete/{p}"), timeout=TIMEOUT)
            ok = ok and r.status_code in (200, 404)
        except requests.RequestException as exc:
            logger.warning("MediaMTX delete failed for %s: %s", p, exc)
            ok = False
    return ok


def get_path_status(camera):
    """Return MediaMTX runtime info for a camera path, or None."""
    name = path_name_for(camera)
    try:
        r = requests.get(_api(f"/v3/paths/get/{name}"), timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def path_is_configured(camera):
    """
    True if MediaMTX currently has a CONFIG entry for this camera's path.
    Paths are added at runtime via the API, so a MediaMTX restart drops them —
    this lets a background task detect and re‑push only the missing ones without
    disturbing paths that already exist (and their live viewers).
    """
    name = path_name_for(camera)
    try:
        r = requests.get(_api(f"/v3/config/paths/get/{name}"), timeout=TIMEOUT)
        return r.status_code == 200
    except requests.RequestException:
        return False


def is_camera_ready(camera):
    """True if MediaMTX reports the source as connected/ready."""
    info = get_path_status(camera)
    if not info:
        return False
    return bool(info.get("ready"))


def playback_urls(camera):
    """
    URLs the browser uses to view the live stream. For HEVC cameras the
    WebRTC/HLS URLs point at the transcoded H.264 path; RTSP stays native.
    """
    native = path_name_for(camera)
    web = web_path_name_for(camera)
    return {
        "webrtc": f"{settings.MEDIAMTX['WEBRTC_URL'].rstrip('/')}/{web}/whep",
        "hls": f"{settings.MEDIAMTX['HLS_URL'].rstrip('/')}/{web}/index.m3u8",
        "rtsp": f"rtsp://{settings.MEDIAMTX['RTSP_HOST']}:{settings.MEDIAMTX['RTSP_PORT']}/{native}",
        "codec": main_codec(camera),
    }


_SAFE = re.compile(r"[^a-zA-Z0-9_]")
