"""
ONVIF helpers: network discovery, profile/stream-URI retrieval and PTZ moves.

Uses onvif-zeep (WSDL client). All functions degrade gracefully — if the
library or the device is unavailable they return empty/False rather than
raising, so the API stays responsive.
"""
import logging

logger = logging.getLogger(__name__)


def discover(timeout=4):
    """
    WS-Discovery scan of the local network for ONVIF devices.
    Returns a list of {xaddr, host, port} dicts.
    """
    try:
        from onvif import ONVIFService  # noqa: F401  (ensures package present)
        from wsdiscovery.discovery import ThreadedWSDiscovery
        from wsdiscovery import QName
    except Exception as exc:  # pragma: no cover - optional dep
        logger.info("WS-Discovery unavailable: %s", exc)
        return []

    found = []
    try:
        wsd = ThreadedWSDiscovery()
        wsd.start()
        services = wsd.searchServices(timeout=timeout)
        for svc in services:
            for xaddr in svc.getXAddrs():
                host, port = _split_xaddr(xaddr)
                found.append({"xaddr": xaddr, "host": host, "port": port})
        wsd.stop()
    except Exception as exc:  # pragma: no cover
        logger.warning("discovery error: %s", exc)
    return found


def get_stream_uri(host, port, username, password):
    """Return the primary RTSP stream URI advertised by an ONVIF device."""
    cam = _connect(host, port, username, password)
    if not cam:
        return None
    try:
        media = cam.create_media_service()
        profiles = media.GetProfiles()
        if not profiles:
            return None
        token = profiles[0].token
        req = media.create_type("GetStreamUri")
        req.ProfileToken = token
        req.StreamSetup = {
            "Stream": "RTP-Unicast",
            "Transport": {"Protocol": "RTSP"},
        }
        uri = media.GetStreamUri(req)
        return uri.Uri
    except Exception as exc:
        logger.warning("GetStreamUri failed: %s", exc)
        return None


def get_device_info(host, port, username, password):
    cam = _connect(host, port, username, password)
    if not cam:
        return {}
    try:
        dev = cam.devicemgmt.GetDeviceInformation()
        return {
            "manufacturer": getattr(dev, "Manufacturer", ""),
            "model": getattr(dev, "Model", ""),
            "firmware": getattr(dev, "FirmwareVersion", ""),
        }
    except Exception:
        return {}


def ptz_move(camera, pan=0.0, tilt=0.0, zoom=0.0):
    """Continuous PTZ move. pan/tilt/zoom in [-1, 1]. Returns True on success."""
    cam = _connect(
        camera.onvif_host or camera.host,
        camera.onvif_port,
        camera.username,
        camera.password,
    )
    if not cam:
        return False
    try:
        media = cam.create_media_service()
        ptz = cam.create_ptz_service()
        token = media.GetProfiles()[0].token
        req = ptz.create_type("ContinuousMove")
        req.ProfileToken = token
        req.Velocity = {
            "PanTilt": {"x": pan, "y": tilt},
            "Zoom": {"x": zoom},
        }
        ptz.ContinuousMove(req)
        return True
    except Exception as exc:
        logger.warning("ptz_move failed: %s", exc)
        return False


def ptz_stop(camera):
    cam = _connect(
        camera.onvif_host or camera.host, camera.onvif_port, camera.username, camera.password
    )
    if not cam:
        return False
    try:
        media = cam.create_media_service()
        ptz = cam.create_ptz_service()
        token = media.GetProfiles()[0].token
        ptz.Stop({"ProfileToken": token, "PanTilt": True, "Zoom": True})
        return True
    except Exception:
        return False


def ptz_goto_preset(camera, token):
    cam = _connect(
        camera.onvif_host or camera.host, camera.onvif_port, camera.username, camera.password
    )
    if not cam:
        return False
    try:
        media = cam.create_media_service()
        ptz = cam.create_ptz_service()
        profile_token = media.GetProfiles()[0].token
        ptz.GotoPreset({"ProfileToken": profile_token, "PresetToken": token})
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
def _connect(host, port, username, password):
    try:
        from onvif import ONVIFCamera
    except Exception as exc:  # pragma: no cover
        logger.info("onvif-zeep unavailable: %s", exc)
        return None
    try:
        return ONVIFCamera(host, int(port or 80), username, password)
    except Exception as exc:
        logger.warning("ONVIF connect failed (%s:%s): %s", host, port, exc)
        return None


def _split_xaddr(xaddr):
    # xaddr like http://192.168.1.10:80/onvif/device_service
    try:
        rest = xaddr.split("://", 1)[1]
        hostport = rest.split("/", 1)[0]
        if ":" in hostport:
            host, port = hostport.split(":", 1)
            return host, int(port)
        return hostport, 80
    except Exception:
        return xaddr, 80
