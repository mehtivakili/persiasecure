"""
RTSP frame acquisition (Phase AI-1).

Decodes a camera's RTSP stream to JPEG frames at a controlled FPS via a single
long-lived ffmpeg process (`-f image2pipe -vcodec mjpeg`). MJPEG is chosen over
raw video so each frame is a self-delimiting JPEG we can hand straight to the
detector (which already takes JPEG bytes) — no numpy needed to move pixels
around, and the byte-level frame splitter is pure Python and unit-testable.

Design notes:
  * One ffmpeg per camera, decoded once — never a second full-resolution decode.
  * `fps` + `scale` keep bandwidth/CPU bounded before the model even runs; the
    MotionGate then skips static frames so the GPU only sees real activity.
  * TCP transport (matches the rest of the stack) and a hard reconnect loop so a
    flaky camera self-heals instead of killing the worker.
"""
import logging
import subprocess

logger = logging.getLogger(__name__)

_SOI = b"\xff\xd8"  # JPEG start-of-image
_EOI = b"\xff\xd9"  # JPEG end-of-image


def extract_jpeg_frames(buffer: bytes):
    """
    Split a raw MJPEG byte buffer into complete JPEG frames.
    Returns (frames, remainder): `frames` is a list of complete JPEG byte
    strings; `remainder` is the trailing partial frame to carry into the next
    read. Pure function — the core of the stream parser, unit-tested.
    """
    frames = []
    pos = 0
    n = len(buffer)
    while True:
        start = buffer.find(_SOI, pos)
        if start < 0:
            return frames, b""
        end = buffer.find(_EOI, start + 2)
        if end < 0:
            return frames, buffer[start:]  # partial frame; keep from SOI
        end += 2
        frames.append(buffer[start:end])
        pos = end
        if pos >= n:
            return frames, b""


class RtspFrameSource:
    """
    Iterable of JPEG frames from an RTSP URL. Use as a context manager:

        with RtspFrameSource(url, fps=5, width=640) as src:
            for jpeg in src:
                ...

    Yields until closed or the ffmpeg process ends; the caller (CameraWorker)
    owns reconnect/backoff.
    """

    def __init__(self, url, fps=5, width=640, read_size=65536):
        self.url = url
        self.fps = fps
        self.width = width
        self.read_size = read_size
        self._proc = None

    def _cmd(self):
        return [
            "ffmpeg", "-nostdin", "-loglevel", "error",
            "-rtsp_transport", "tcp", "-i", self.url,
            "-vf", f"fps={self.fps},scale={self.width}:-1",
            "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "5", "-",
        ]

    def __enter__(self):
        self._proc = subprocess.Popen(
            self._cmd(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
        )
        return self

    def __iter__(self):
        buf = b""
        assert self._proc is not None and self._proc.stdout is not None
        while True:
            chunk = self._proc.stdout.read(self.read_size)
            if not chunk:
                break
            buf += chunk
            frames, buf = extract_jpeg_frames(buf)
            for f in frames:
                yield f

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
