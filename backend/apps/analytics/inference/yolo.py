"""
YOLO object detector on ONNX Runtime (Phase AI‑0 real backend).

Decodes a standard Ultralytics YOLOv8/v11 ONNX export:
    input  : (1, 3, H, W) float32, RGB, 0..1, letterboxed
    output : (1, 4+num_classes, num_anchors) — [cx, cy, w, h, class_scores...]

`numpy` and `onnxruntime` are **optional**. If either is missing (as in the
lightweight test image) or the weights file is absent, `available()` returns
False and the runner falls back to the legacy detector — the alarm loop never
sees an ImportError. On a GPU host, install `onnxruntime-gpu` and set the
model's `device="cuda"` to use the CUDA execution provider.

The pixel decode/NMS math lives in `geometry` (pure Python, unit‑tested); this
module only handles tensor I/O, which requires the heavy libs.
"""
import io
import logging
import threading

from . import geometry
from .base import Detector, RawDetection

logger = logging.getLogger(__name__)

try:  # optional heavy deps — absent in the test image, present on inference hosts
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - exercised only where numpy is absent
    np = None

try:
    import onnxruntime as ort  # type: ignore
except Exception:  # pragma: no cover
    ort = None


# Ordered COCO class names (index → label) for stock YOLO exports.
COCO_CLASSES = [
    "person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "sofa",
    "pottedplant", "bed", "diningtable", "toilet", "tvmonitor", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


class YoloOnnxDetector(Detector):
    task = "object"

    def __init__(self, model=None):
        super().__init__(model)
        self._session = None
        self._input_name = None
        self._lock = threading.Lock()

    # -- availability ------------------------------------------------------
    def available(self) -> bool:
        if np is None or ort is None:
            return False
        path = getattr(self.model, "path", "") or ""
        if not path:
            return False
        try:
            return self._ensure_session()
        except Exception as exc:  # pragma: no cover - depends on real weights
            logger.warning("YOLO model unavailable (%s): %s", path, exc)
            return False

    def _providers(self):
        if getattr(self.model, "device", "cpu") == "cuda":
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def _ensure_session(self) -> bool:
        if self._session is not None:
            return True
        with self._lock:
            if self._session is not None:
                return True
            self._session = ort.InferenceSession(self.model.path, providers=self._providers())
            self._input_name = self._session.get_inputs()[0].name
        return True

    def warmup(self):  # pragma: no cover - needs real weights
        if self.available() and np is not None:
            w = int(getattr(self.model, "input_w", 640))
            h = int(getattr(self.model, "input_h", 640))
            blank = np.zeros((1, 3, h, w), dtype=np.float32)
            self._session.run(None, {self._input_name: blank})

    # -- inference ---------------------------------------------------------
    def _classes(self):
        return (getattr(self.model, "classes", None) or COCO_CLASSES)

    def _preprocess(self, image_bytes):  # pragma: no cover - needs numpy
        """JPEG bytes → (CHW float tensor, src_w, src_h, letterbox params)."""
        from PIL import Image

        in_w = int(getattr(self.model, "input_w", 640))
        in_h = int(getattr(self.model, "input_h", 640))
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        src_w, src_h = img.size
        scale, pad_x, pad_y = geometry.letterbox_params(src_w, src_h, in_w, in_h)
        resized = img.resize((max(1, int(src_w * scale)), max(1, int(src_h * scale))))
        canvas = Image.new("RGB", (in_w, in_h), (114, 114, 114))
        canvas.paste(resized, (int(pad_x), int(pad_y)))
        arr = np.asarray(canvas, dtype=np.float32) / 255.0
        chw = np.transpose(arr, (2, 0, 1))     # (3,H,W)
        return chw, src_w, src_h, (scale, pad_x, pad_y)

    def _decode(self, preds, src_w, src_h, lb):  # pragma: no cover - needs numpy
        """One frame's raw model output (C+4, N) → RawDetection[]."""
        min_conf = float(getattr(self.model, "min_confidence", 0.35))
        iou_thr = float(getattr(self.model, "iou_threshold", 0.45))
        classes = self._classes()
        scale, pad_x, pad_y = lb
        if preds.shape[0] < preds.shape[1]:
            preds = preds.transpose()           # → (N, 4+C)
        dets = []
        for row in preds:
            cx, cy, bw, bh = row[0], row[1], row[2], row[3]
            scores = row[4:]
            cls_id = int(np.argmax(scores))
            conf = float(scores[cls_id])
            if conf < min_conf or cls_id >= len(classes):
                continue
            box = [cx - bw / 2.0, cy - bh / 2.0, cx + bw / 2.0, cy + bh / 2.0]
            nx = geometry.unletterbox_xyxy(box, scale, pad_x, pad_y, src_w, src_h)
            dets.append({"label": classes[cls_id], "confidence": conf,
                         "bbox": geometry.xyxy_to_xywh(nx), "class_id": cls_id})
        kept = geometry.per_class_nms(dets, iou_thr)
        # Coerce numpy scalars to Python float — Event.details is a JSONField and
        # np.float32 is not JSON-serializable (would crash on Event creation).
        return [
            RawDetection(label=d["label"], confidence=round(float(d["confidence"]), 4),
                         bbox=[round(float(v), 4) for v in d["bbox"]],
                         extra={"class_id": int(d["class_id"])})
            for d in kept
        ]

    def infer(self, image_bytes, width, height):  # pragma: no cover - needs real weights + numpy
        if not self.available():
            return []
        chw, src_w, src_h, lb = self._preprocess(image_bytes)
        tensor = chw[None, ...]                  # (1,3,H,W)
        out = self._session.run(None, {self._input_name: tensor})[0]
        return self._decode(np.squeeze(out, 0), src_w, src_h, lb)

    def infer_batch(self, frames):  # pragma: no cover - needs real weights + numpy
        """One batched forward pass over many frames (GPU throughput)."""
        if not self.available() or not frames:
            return [[] for _ in frames]
        pre = [self._preprocess(img) for (img, _w, _h) in frames]
        batch = np.stack([p[0] for p in pre], axis=0)   # (B,3,H,W)
        out = self._session.run(None, {self._input_name: batch})[0]  # (B, 4+C, N)
        results = []
        for i, (_chw, src_w, src_h, lb) in enumerate(pre):
            results.append(self._decode(out[i], src_w, src_h, lb))
        return results
