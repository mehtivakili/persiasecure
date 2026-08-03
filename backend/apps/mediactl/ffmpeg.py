"""ffmpeg helpers: snapshots and lightweight motion sampling."""
import json
import logging
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# Codecs the browser pipeline supports (h264 natively; hevc/h265 recorded and
# transcoded on demand). Anything else is reachable but "unsupported".
SUPPORTED_CODECS = {"h264", "hevc", "h265"}


def grab_snapshot(rtsp_url, timeout=15):
    """
    Capture a single JPEG frame from an RTSP URL. Returns bytes or None.
    Used for camera thumbnails and event frames.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    cmd = [
        "ffmpeg",
        "-y",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-frames:v",
        "1",
        "-q:v",
        "3",
        tmp.name,
    ]
    try:
        subprocess.run(
            cmd,
            timeout=timeout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        with open(tmp.name, "rb") as fh:
            return fh.read()
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("snapshot failed: %s", exc)
        return None


def _classify_error(stderr):
    """Map ffprobe stderr onto a structured, actionable reason code."""
    s = (stderr or "").lower()
    if any(k in s for k in ("401", "403", "unauthorized", "authentication", "auth failed")):
        return "auth"
    if any(
        k in s
        for k in (
            "could not resolve",
            "name or service not known",
            "failure in name resolution",
            "no address associated with hostname",
        )
    ):
        return "dns"
    if any(
        k in s
        for k in (
            "connection refused",
            "no route to host",
            "connection timed out",
            "network is unreachable",
            "timed out",
            "i/o error",
            "immediate exit requested",
        )
    ):
        return "network"
    if any(k in s for k in ("unsupported", "codec not currently supported", "decoder")):
        return "unsupported_codec"
    return "unknown"


def probe_source(rtsp_url, timeout=12, transport="tcp"):
    """
    Probe an RTSP source and return a structured result the UI can act on:

        {
          "ok": bool,               # a supported video stream was read
          "reachable": bool,        # the source was reached and produced a stream
          "reason": str,            # ok | unsupported_codec | auth | dns |
                                    #   network | timeout | ffprobe_missing | unknown
          "codec": str | None,      # detected video codec when reachable
          "width": int | None,
          "height": int | None,
          "detail": str,            # trimmed ffprobe stderr for diagnostics
        }
    """
    cmd = [
        "ffprobe",
        "-rtsp_transport",
        transport or "tcp",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height",
        "-of",
        "json",
        rtsp_url,
    ]
    try:
        out = subprocess.run(cmd, timeout=timeout, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reachable": False, "reason": "timeout", "codec": None,
                "width": None, "height": None, "detail": ""}
    except FileNotFoundError:
        logger.error("ffprobe not found on PATH — cannot test camera connectivity.")
        return {"ok": False, "reachable": False, "reason": "ffprobe_missing", "codec": None,
                "width": None, "height": None, "detail": "ffprobe not installed"}
    except subprocess.SubprocessError as exc:
        return {"ok": False, "reachable": False, "reason": "unknown", "codec": None,
                "width": None, "height": None, "detail": str(exc)}

    if out.returncode == 0 and "codec_name" in (out.stdout or ""):
        codec = width = height = None
        try:
            streams = json.loads(out.stdout).get("streams", [])
            if streams:
                codec = (streams[0].get("codec_name") or "").lower() or None
                width = streams[0].get("width")
                height = streams[0].get("height")
        except (ValueError, TypeError):
            pass
        supported = codec in SUPPORTED_CODECS
        return {
            "ok": supported,
            "reachable": True,
            "reason": "ok" if supported else "unsupported_codec",
            "codec": codec,
            "width": width,
            "height": height,
            "detail": "",
        }

    return {
        "ok": False,
        "reachable": False,
        "reason": _classify_error(out.stderr),
        "codec": None,
        "width": None,
        "height": None,
        "detail": (out.stderr or "").strip()[-400:],
    }


def probe_connectivity(rtsp_url, timeout=10):
    """Backwards‑compatible boolean probe (see :func:`probe_source`)."""
    return probe_source(rtsp_url, timeout=timeout).get("reachable", False)
