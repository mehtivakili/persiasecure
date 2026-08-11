"""
Motion gate (Phase AI-1).

The single biggest GPU/CPU saving in multi-camera CV: only run the (expensive)
model on frames where *something changed*. A static corridor at 3 a.m. produces
zero inference load. Implemented as a cheap grayscale frame-difference on a
tiny downsample (Pillow only — no numpy), mirroring the existing motion worker's
approach so behaviour is consistent across the product.
"""
import io
import logging

logger = logging.getLogger(__name__)


class MotionGate:
    """
    `passes(jpeg_bytes)` returns True when the frame differs enough from the
    previous one to be worth running detection on. The first frame always
    passes (no baseline yet). On decode error it fails open (returns True) so a
    gate glitch never silently blinds a camera.
    """

    def __init__(self, threshold=2.0, size=(64, 36)):
        self.threshold = float(threshold)
        self.size = size
        self._prev = None
        self.last_score = 0.0

    def _luma(self, jpeg_bytes):
        from PIL import Image

        img = Image.open(io.BytesIO(jpeg_bytes)).convert("L").resize(self.size)
        return img

    def passes(self, jpeg_bytes) -> bool:
        try:
            cur = self._luma(jpeg_bytes)
        except Exception as exc:
            logger.debug("motion gate decode failed, failing open: %s", exc)
            return True
        if self._prev is None:
            self._prev = cur
            self.last_score = float("inf")
            return True
        from PIL import ImageChops, ImageStat

        diff = ImageChops.difference(self._prev, cur)
        self.last_score = ImageStat.Stat(diff).mean[0]
        self._prev = cur
        return self.last_score >= self.threshold

    def reset(self):
        self._prev = None
        self.last_score = 0.0
