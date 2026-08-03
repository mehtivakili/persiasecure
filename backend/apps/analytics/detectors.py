"""
Pluggable detector layer.

Real ALPR/object models are heavy and environment-specific, so detectors are
optional and degrade gracefully: if the backing library/model is not installed
they return an empty result instead of raising. Swap in OpenALPR, a YOLO/ONNX
model or a cloud API by implementing the two functions below — the rest of the
pipeline (tasks.py) and the API stay unchanged.

This mirrors Shinobi's plugin approach (openalpr / opencv plugins).
"""
import logging
import random

from django.conf import settings

logger = logging.getLogger(__name__)

# Default COCO-ish classes an object detector might emit.
DEFAULT_CLASSES = ["person", "car", "truck", "bus", "motorbike", "bicycle"]

# Demo-mode fixtures (rule config {"demo": true}): lets the whole pipeline —
# workers, watchlist matching, events, WebSocket feed, UI tables — be exercised
# end-to-end before a real ALPR/object model is installed. Clearly synthetic.
DEMO_PLATES = ["12ب34567", "45د67890", "78س12345", "11الف22333"]
DEMO_OBJECTS = ["person", "car", "truck"]


def _demo_enabled(config):
    """True only when both the deployment and the individual rule opt in."""
    return bool(
        getattr(settings, "ENABLE_DEMO_ANALYTICS", False)
        and (config or {}).get("demo")
    )


def detect_plates(image_bytes, config=None):
    """
    Return a list of {plate, confidence, country} from a JPEG frame.
    Demo mode (config.demo) emits synthetic reads; otherwise tries OpenALPR
    (python binding) if installed, else returns [].
    """
    config = config or {}
    country = config.get("country", "ir")
    if _demo_enabled(config):
        # Emit 0–1 synthetic plates per sample so the feed looks organic.
        if random.random() < float(config.get("demo_rate", 0.7)):
            return [
                {
                    "plate": random.choice(config.get("demo_plates", DEMO_PLATES)),
                    "confidence": round(random.uniform(82, 99), 1),
                    "country": country,
                }
            ]
        return []
    try:
        from openalpr import Alpr  # type: ignore
    except Exception:
        logger.debug("OpenALPR not installed — ALPR detector is a no-op.")
        return []

    alpr = None
    try:
        alpr = Alpr(country, "/etc/openalpr/openalpr.conf", "/usr/share/openalpr/runtime_data")
        if not alpr.is_loaded():
            return []
        results = alpr.recognize_array(image_bytes)
        out = []
        min_conf = float(config.get("min_confidence", 75))
        for plate in results.get("results", []):
            conf = plate.get("confidence", 0)
            if conf >= min_conf:
                out.append(
                    {"plate": plate["plate"], "confidence": conf, "country": country}
                )
        return out
    except Exception as exc:  # pragma: no cover
        logger.warning("ALPR error: %s", exc)
        return []
    finally:
        if alpr is not None:
            alpr.unload()


def detect_objects(image_bytes, config=None):
    """
    Return a list of {label, confidence, bbox} from a JPEG frame.
    Uses an OpenCV DNN model if `model`/`config_path` are provided in config
    and OpenCV is installed; otherwise returns [].
    """
    config = config or {}
    if _demo_enabled(config):
        if random.random() < float(config.get("demo_rate", 0.5)):
            label = random.choice(config.get("demo_objects", DEMO_OBJECTS))
            x, y = round(random.uniform(0.1, 0.6), 3), round(random.uniform(0.1, 0.6), 3)
            return [
                {
                    "label": label,
                    "confidence": round(random.uniform(60, 97), 1),
                    "bbox": [x, y, 0.25, 0.3],
                }
            ]
        return []
    model_path = config.get("model")
    cfg_path = config.get("config_path")
    if not model_path or not cfg_path:
        logger.debug("No object model configured — object detector is a no-op.")
        return []
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        logger.debug("OpenCV/numpy not installed — object detector is a no-op.")
        return []

    try:
        net = cv2.dnn.readNet(model_path, cfg_path)
        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]
        blob = cv2.dnn.blobFromImage(img, 1 / 255.0, (416, 416), swapRB=True, crop=False)
        net.setInput(blob)
        classes = config.get("classes", DEFAULT_CLASSES)
        min_conf = float(config.get("min_confidence", 0.5))
        detections = []
        for output in net.forward(_output_layers(net)):
            for det in output:
                scores = det[5:]
                class_id = int(np.argmax(scores))
                conf = float(scores[class_id])
                if conf >= min_conf and class_id < len(classes):
                    cx, cy, bw, bh = det[0:4]
                    detections.append(
                        {
                            "label": classes[class_id],
                            "confidence": round(conf * 100, 1),
                            "bbox": [
                                round(float(cx - bw / 2), 4),
                                round(float(cy - bh / 2), 4),
                                round(float(bw), 4),
                                round(float(bh), 4),
                            ],
                        }
                    )
        return detections
    except Exception as exc:  # pragma: no cover
        logger.warning("object detect error: %s", exc)
        return []


def _output_layers(net):
    names = net.getLayerNames()
    return [names[i - 1] for i in net.getUnconnectedOutLayers().flatten()]


# ---------------------------------------------------------------------------
# Fire / smoke — classic colorimetric heuristics (Pillow only, no ML deps).
# fire: ratio of "flame-colored" pixels (hot red/orange, R≫B) above threshold.
# smoke: ratio of low-saturation mid-gray pixels above threshold.
# Tune per scene via rule config; demo mode exercises the alarm pipeline.
# Swap for an ML model here without touching tasks/API.
# ---------------------------------------------------------------------------

def detect_fire(image_bytes, config=None):
    """Return {detected, ratio} for flame-colored regions in the frame."""
    config = config or {}
    if _demo_enabled(config):
        if random.random() < float(config.get("demo_rate", 0.15)):
            return {"detected": True, "ratio": round(random.uniform(0.05, 0.2), 3), "demo": True}
        return {"detected": False, "ratio": 0.0, "demo": True}

    min_ratio = float(config.get("min_ratio", 0.02))  # ≥2% of pixels flame-like
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((160, 90))
        px = img.load()
        w, h = img.size
        hot = 0
        for y in range(h):
            for x in range(w):
                r, g, b = px[x, y]
                # Flame signature: strong red, red dominates blue heavily,
                # green between blue and red (orange/yellow band), bright.
                if r > 190 and r > b + 90 and b < 120 and g > b:
                    hot += 1
        ratio = hot / float(w * h)
        return {"detected": ratio >= min_ratio, "ratio": round(ratio, 4)}
    except Exception as exc:
        logger.warning("fire detect error: %s", exc)
        return {"detected": False, "ratio": 0.0}


def detect_smoke(image_bytes, config=None):
    """Return {detected, ratio} for smoke-like (desaturated haze) regions."""
    config = config or {}
    if _demo_enabled(config):
        if random.random() < float(config.get("demo_rate", 0.15)):
            return {"detected": True, "ratio": round(random.uniform(0.2, 0.5), 3), "demo": True}
        return {"detected": False, "ratio": 0.0, "demo": True}

    min_ratio = float(config.get("min_ratio", 0.35))  # ≥35% hazy grey pixels
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((160, 90))
        px = img.load()
        w, h = img.size
        hazy = 0
        for y in range(h):
            for x in range(w):
                r, g, b = px[x, y]
                mx, mn = max(r, g, b), min(r, g, b)
                # Smoke signature: low saturation, mid-to-light grey.
                if (mx - mn) < 22 and 110 <= mx <= 225:
                    hazy += 1
        ratio = hazy / float(w * h)
        return {"detected": ratio >= min_ratio, "ratio": round(ratio, 4)}
    except Exception as exc:
        logger.warning("smoke detect error: %s", exc)
        return {"detected": False, "ratio": 0.0}
