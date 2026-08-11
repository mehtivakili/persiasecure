"""
Lightweight IoU tracker (Phase AI-1).

Assigns a **stable `track_id`** to each object across frames using greedy
IoU matching (a compact ByteTrack-style association without the Kalman filter).
Stable ids are what turn per-frame detections into intelligence:

  * **Dedup that actually works** — the Phase-7 pipeline suppresses duplicates by
    track_id, so one person loitering for 10 s is one alarm, not 50.
  * **Direction / line-crossing** — a track's centroid history tells you which way
    it crossed a tripwire (the object-based upgrade over pixel motion).
  * **Dwell / counting** — first_seen…last_seen per track.

Pure Python (no numpy), so it is fully unit-tested and runs anywhere. Boxes are
`[x, y, w, h]` normalized 0..1.
"""
from . import geometry


class _Track:
    __slots__ = ("id", "bbox", "label", "age", "hits", "centroids")

    def __init__(self, tid, bbox, label):
        self.id = tid
        self.bbox = bbox
        self.label = label
        self.age = 0          # frames since last matched
        self.hits = 1         # total frames matched
        self.centroids = [_centroid(bbox)]


def _centroid(b):
    return (b[0] + b[2] / 2.0, b[1] + b[3] / 2.0)


class IouTracker:
    def __init__(self, iou_threshold=0.3, max_age=30, same_label_only=True):
        self.iou_threshold = float(iou_threshold)
        self.max_age = int(max_age)
        self.same_label_only = same_label_only
        self._tracks = []
        self._next_id = 1

    def update(self, raws):
        """
        Match `raws` (list of RawDetection with `.bbox`/`.label`) to existing
        tracks, mutate each RawDetection's `track_id`, age out stale tracks, and
        return the same list. Highest-IoU pairs are bound first (greedy).
        """
        pairs = []  # (iou, track_index, det_index)
        for ti, track in enumerate(self._tracks):
            tb = geometry.xywh_to_xyxy(track.bbox)
            for di, det in enumerate(raws):
                if self.same_label_only and det.label != track.label:
                    continue
                if not det.bbox:
                    continue
                iou = geometry.iou_xyxy(tb, geometry.xywh_to_xyxy(det.bbox))
                if iou >= self.iou_threshold:
                    pairs.append((iou, ti, di))
        pairs.sort(reverse=True)

        matched_tracks, matched_dets = set(), set()
        for iou, ti, di in pairs:
            if ti in matched_tracks or di in matched_dets:
                continue
            matched_tracks.add(ti)
            matched_dets.add(di)
            track = self._tracks[ti]
            det = raws[di]
            track.bbox = det.bbox
            track.age = 0
            track.hits += 1
            track.centroids.append(_centroid(det.bbox))
            if len(track.centroids) > 64:
                track.centroids.pop(0)
            det.track_id = f"t{track.id}"

        # Unmatched detections → new tracks.
        for di, det in enumerate(raws):
            if di in matched_dets or not det.bbox:
                continue
            track = _Track(self._next_id, det.bbox, det.label)
            self._next_id += 1
            self._tracks.append(track)
            det.track_id = f"t{track.id}"

        # Age unmatched tracks; drop the stale ones.
        for ti, track in enumerate(self._tracks):
            if ti not in matched_tracks:
                track.age += 1
        self._tracks = [t for t in self._tracks if t.age <= self.max_age]

        return raws

    @property
    def active_count(self):
        return len(self._tracks)
