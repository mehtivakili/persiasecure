"""
Detector registry + hardware health (Phase AI‑0).

Resolves the active `DetectorModel` for a task into a loaded `Detector`, caching
the instance so ONNX sessions are built once per model build (keyed by id +
`updated_at`, so activating a new/edited model transparently reloads). Also
provides a best‑effort GPU/CPU snapshot for the detector‑health endpoint.
"""
import logging
import subprocess

from .dummy import DummyDetector
from .plates import DummyPlateDetector, YoloPlateOcrDetector
from .yolo import YoloOnnxDetector

logger = logging.getLogger(__name__)

# model_id -> (updated_at_iso, Detector)
_INSTANCES = {}

# Backend class per (task, framework). A task needs its own backend because the
# model output differs — an object YOLO vs a plate-detect+OCR head.
_BACKENDS = {
    ("object", "dummy"): DummyDetector,
    ("object", "onnx"): YoloOnnxDetector,
    ("alpr", "dummy"): DummyPlateDetector,
    ("alpr", "onnx"): YoloPlateOcrDetector,
}


def _build(model):
    cls = _BACKENDS.get((model.task, model.framework))
    if cls is None:
        logger.debug("No inference backend for task=%s framework=%s", model.task, model.framework)
        return None
    return cls(model)


def get_detector(task):
    """
    Return a ready `Detector` for the newest active model of `task`, or None
    when there is no active model or its backend/weights are unavailable.
    Never raises.
    """
    from apps.analytics.models import DetectorModel

    model = DetectorModel.active_for(task)
    if model is None:
        return None
    stamp = model.updated_at.isoformat() if model.updated_at else ""
    cached = _INSTANCES.get(model.id)
    if cached and cached[0] == stamp:
        detector = cached[1]
    else:
        detector = _build(model)
        if detector is None:
            return None
        _INSTANCES[model.id] = (stamp, detector)
    try:
        if not detector.available():
            return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("detector.available() raised for %s: %s", model, exc)
        return None
    return detector


def has_active_model(task) -> bool:
    from apps.analytics.models import DetectorModel

    return DetectorModel.objects.filter(task=task, active=True).exists()


def clear_cache():
    _INSTANCES.clear()


def hardware_snapshot() -> dict:
    """
    Best‑effort GPU/CPU snapshot for monitoring. Returns {} when nothing is
    detectable (e.g. CPU‑only host without nvidia‑smi). Never raises.
    """
    snap = {}
    try:
        import os

        if hasattr(os, "getloadavg"):
            load1, load5, load15 = os.getloadavg()
            snap["cpu_load"] = {"1m": round(load1, 2), "5m": round(load5, 2), "15m": round(load15, 2)}
            snap["cpu_count"] = os.cpu_count()
    except Exception:  # pragma: no cover
        pass

    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4,
        )
        if out.returncode == 0 and out.stdout.strip():
            gpus = []
            for line in out.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    gpus.append({
                        "index": parts[0], "name": parts[1],
                        "util_percent": _num(parts[2]),
                        "mem_used_mb": _num(parts[3]), "mem_total_mb": _num(parts[4]),
                        "temp_c": _num(parts[5]),
                    })
            if gpus:
                snap["gpus"] = gpus
    except (FileNotFoundError, subprocess.SubprocessError):
        pass  # no GPU / no driver — expected on CPU hosts
    except Exception:  # pragma: no cover
        pass
    return snap


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return s
