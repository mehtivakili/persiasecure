"""
Motion heatmap accumulation and tripwire (line-crossing) scoring.

Both operate on the frame-difference image the motion pipeline already
produces, so they add no extra camera load.
"""
import logging
from datetime import timedelta

from django.utils import timezone

from .models import MotionHeatmap

logger = logging.getLogger(__name__)

DIFF_THRESHOLD = 25  # pixel |Δ| above this counts as "changed"


def accumulate(camera, diff_img):
    """
    Add one frame-diff sample into today's heatmap grid for the camera.
    diff_img: PIL 'L' image (abs difference of two frames).
    """
    try:
        from PIL import Image

        W, H = MotionHeatmap.GRID_W, MotionHeatmap.GRID_H
        # Binarize, then BOX-downsample: each cell = fraction of changed px ×255.
        binary = diff_img.point(lambda p: 255 if p > DIFF_THRESHOLD else 0)
        cells = binary.resize((W, H), Image.BOX)
        px = cells.load()

        today = timezone.localdate()
        hm, _ = MotionHeatmap.objects.get_or_create(
            camera=camera,
            date=today,
            defaults={
                "organization": camera.organization,
                "grid": [[0] * W for _ in range(H)],
            },
        )
        grid = hm.grid or [[0] * W for _ in range(H)]
        for y in range(H):
            row = grid[y]
            for x in range(W):
                v = px[x, y]
                if v:
                    row[x] += v // 16  # 0..15 per sample keeps ints small
        hm.grid = grid
        hm.samples += 1
        hm.save(update_fields=["grid", "samples"])
    except Exception as exc:  # heatmap must never break detection
        logger.debug("heatmap accumulate failed: %s", exc)


def summarize(camera, days=7):
    """Sum the camera's grids over the last `days`; returns dict for the API."""
    W, H = MotionHeatmap.GRID_W, MotionHeatmap.GRID_H
    since = timezone.localdate() - timedelta(days=max(days - 1, 0))
    total = [[0] * W for _ in range(H)]
    samples = 0
    for hm in MotionHeatmap.objects.filter(camera=camera, date__gte=since):
        samples += hm.samples
        g = hm.grid or []
        for y in range(min(H, len(g))):
            row = g[y]
            for x in range(min(W, len(row))):
                total[y][x] += row[x]
    peak = max((v for row in total for v in row), default=0)
    return {"w": W, "h": H, "grid": total, "max": peak, "samples": samples, "days": days}


def line_score(diff_img, line, width_frac=0.05):
    """
    Mean |Δ| of pixels inside a corridor around a normalized line
    [[x1,y1],[x2,y2]] (0..1 coords). High mean ⇒ something crossed the line.
    """
    try:
        from PIL import Image, ImageDraw, ImageStat

        w, h = diff_img.size
        (x1, y1), (x2, y2) = line
        p1 = (int(x1 * w), int(y1 * h))
        p2 = (int(x2 * w), int(y2 * h))
        corridor = max(2, int(((w ** 2 + h ** 2) ** 0.5) * width_frac))
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.line([p1, p2], fill=255, width=corridor)
        return ImageStat.Stat(diff_img, mask).mean[0]
    except Exception as exc:
        logger.debug("line_score failed: %s", exc)
        return 0.0
