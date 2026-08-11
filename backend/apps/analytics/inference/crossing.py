"""
Object-based line crossing (Phase AI-5, built on the AI-1 tracker).

The pixel tripwire (`tasks.tripwire_worker`) fires on *any* motion near a line —
sunlight, shadows, a swaying plant. This is the real thing: a **tracked object's
centroid path** crossing the line, with the **direction** of travel. One person
walking through "عبور از خط لابی ۳" produces exactly one directional crossing
event, not a burst of pixel noise.

Pure geometry (segment intersection + orientation), so it is fully unit-tested
and has no model/deps. Points are normalized 0..1 `(x, y)`.
"""


def orient(a, b, c):
    """Signed area ×2 of triangle abc: >0 left turn, <0 right, 0 collinear."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, c):
    """True if collinear point c lies within segment ab's bounding box."""
    return (min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))


def segments_intersect(p1, p2, q1, q2):
    """Do segment p1p2 and segment q1q2 intersect (including touching)?"""
    d1, d2 = orient(q1, q2, p1), orient(q1, q2, p2)
    d3, d4 = orient(p1, p2, q1), orient(p1, p2, q2)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    # Collinear / endpoint-touching edge cases.
    if d1 == 0 and _on_segment(q1, q2, p1):
        return True
    if d2 == 0 and _on_segment(q1, q2, p2):
        return True
    if d3 == 0 and _on_segment(p1, p2, q1):
        return True
    if d4 == 0 and _on_segment(p1, p2, q2):
        return True
    return False


class LineCrossingDetector:
    """
    Feed per-track centroids frame by frame; get a direction label ("ab"/"ba")
    the frame a track crosses the line, else None. `direction` filters to one
    way ("ab", "ba") or "both". Tracks are remembered by id so the previous
    centroid forms the movement segment.
    """

    def __init__(self, line, direction="both", max_tracks=512):
        self.a = tuple(line[0])
        self.b = tuple(line[1])
        self.direction = direction
        self.max_tracks = max_tracks
        self._last = {}  # track_id -> (x, y)

    def check(self, track_id, centroid):
        prev = self._last.get(track_id)
        self._last[track_id] = centroid
        if len(self._last) > self.max_tracks:            # bound memory
            self._last.pop(next(iter(self._last)))
        if prev is None:
            return None
        if not segments_intersect(prev, centroid, self.a, self.b):
            return None
        # Direction from which side of the line the object moved.
        side_prev = orient(self.a, self.b, prev)
        side_cur = orient(self.a, self.b, centroid)
        if (side_prev > 0) == (side_cur > 0):            # same side → grazed, no real crossing
            return None
        # "ab": moved from the positive side of a→b to the negative side; "ba": reverse.
        crossing = "ab" if side_prev > 0 else "ba"
        if self.direction != "both" and crossing != self.direction:
            return None
        return crossing
