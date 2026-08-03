"""
Playback helpers (Phase 4): signed playback URLs + proper HTTP Range responses.

Recording segments are small (≈1-minute fmp4), so serving them from Django with
correct byte-range support is fine and enables native seeking / continuous
playback in the browser without piping multi-gigabyte files. Access is granted
via short-lived signed tokens minted by the org-scoped timeline endpoint, so a
plain <video src> works (native seeking) without attaching an Authorization
header to every request.
"""
import os
import re

from django.conf import settings
from django.core import signing
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
_SALT = "recording-playback"


def sign_recording(rec_id):
    return signing.dumps(int(rec_id), salt=_SALT)


def verify_recording_sig(token, pk):
    """Return True if `token` is a valid, unexpired signature for recording pk."""
    if not token:
        return False
    ttl = int(getattr(settings, "PLAYBACK_URL_TTL", 6 * 3600))
    try:
        rid = signing.loads(token, salt=_SALT, max_age=ttl)
    except signing.BadSignature:
        return False
    return str(rid) == str(pk)


def signed_stream_url(rec_id):
    # Trailing slash matches the DRF router route so the browser isn't 301'd.
    return f"/api/recordings/{rec_id}/stream/?sig={sign_recording(rec_id)}"


def ranged_file_response(request, path, content_type="video/mp4"):
    """
    Serve `path` honouring the HTTP Range header (206 Partial Content), streaming
    only the requested slice. Falls back to a full 200 response when no range is
    requested.
    """
    if not path or not os.path.exists(path):
        raise Http404("فایل یافت نشد.")
    file_size = os.path.getsize(path)
    range_header = request.META.get("HTTP_RANGE", "")
    match = _RANGE_RE.match(range_header) if range_header else None

    if not match:
        resp = FileResponse(open(path, "rb"), content_type=content_type)
        resp["Accept-Ranges"] = "bytes"
        resp["Content-Length"] = str(file_size)
        return resp

    start = int(match.group(1)) if match.group(1) else 0
    end = int(match.group(2)) if match.group(2) else file_size - 1
    end = min(end, file_size - 1)
    if start > end or start >= file_size:
        resp = HttpResponse(status=416)
        resp["Content-Range"] = f"bytes */{file_size}"
        return resp

    length = end - start + 1

    def _chunks(chunk_size=64 * 1024):
        with open(path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                data = fh.read(min(chunk_size, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    resp = StreamingHttpResponse(_chunks(), status=206, content_type=content_type)
    resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    resp["Accept-Ranges"] = "bytes"
    resp["Content-Length"] = str(length)
    return resp
