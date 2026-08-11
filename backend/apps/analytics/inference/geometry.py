"""
Box geometry: IoU, non‑max suppression, letterbox coordinate mapping.

Pure Python (no numpy) so it is unit‑testable in the lightweight test image and
shared by every detector backend. Boxes are `[x, y, w, h]` unless noted; "xyxy"
means `[x1, y1, x2, y2]`. Normalized coordinates are 0..1.
"""


def xywh_to_xyxy(b):
    x, y, w, h = b[0], b[1], b[2], b[3]
    return [x, y, x + w, y + h]


def xyxy_to_xywh(b):
    x1, y1, x2, y2 = b[0], b[1], b[2], b[3]
    return [x1, y1, x2 - x1, y2 - y1]


def iou_xyxy(a, b):
    """Intersection‑over‑union of two xyxy boxes."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def nms(boxes_xyxy, scores, iou_threshold=0.45, max_out=300):
    """
    Greedy non‑max suppression. `boxes_xyxy` and `scores` are equal‑length
    lists; returns the kept indices, highest score first.
    """
    idxs = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    keep = []
    while idxs and len(keep) < max_out:
        best = idxs.pop(0)
        keep.append(best)
        idxs = [
            i for i in idxs
            if iou_xyxy(boxes_xyxy[best], boxes_xyxy[i]) <= iou_threshold
        ]
    return keep


def per_class_nms(dets, iou_threshold=0.45):
    """
    NMS applied independently within each class label. `dets` is a list of
    dicts with keys `bbox` (xywh normalized), `confidence`, `label`.
    Returns the surviving dets, highest confidence first.
    """
    by_label = {}
    for d in dets:
        by_label.setdefault(d["label"], []).append(d)
    out = []
    for label, group in by_label.items():
        boxes = [xywh_to_xyxy(d["bbox"]) for d in group]
        scores = [d["confidence"] for d in group]
        for i in nms(boxes, scores, iou_threshold):
            out.append(group[i])
    out.sort(key=lambda d: d["confidence"], reverse=True)
    return out


def letterbox_params(src_w, src_h, dst_w, dst_h):
    """
    Scale + padding to fit a src frame into a dst square keeping aspect ratio
    (YOLO "letterbox"). Returns (scale, pad_x, pad_y).
    """
    scale = min(dst_w / float(src_w), dst_h / float(src_h))
    new_w, new_h = src_w * scale, src_h * scale
    pad_x = (dst_w - new_w) / 2.0
    pad_y = (dst_h - new_h) / 2.0
    return scale, pad_x, pad_y


def unletterbox_xyxy(box, scale, pad_x, pad_y, src_w, src_h):
    """
    Map a box from letterboxed model space back to the original frame, returned
    as **normalized** xyxy (0..1). Clamped to the frame.
    """
    x1 = (box[0] - pad_x) / scale
    y1 = (box[1] - pad_y) / scale
    x2 = (box[2] - pad_x) / scale
    y2 = (box[3] - pad_y) / scale
    x1 = min(max(x1, 0.0), src_w)
    y1 = min(max(y1, 0.0), src_h)
    x2 = min(max(x2, 0.0), src_w)
    y2 = min(max(y2, 0.0), src_h)
    return [x1 / src_w, y1 / src_h, x2 / src_w, y2 / src_h]
