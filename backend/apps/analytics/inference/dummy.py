"""
Dummy detector — proves the whole AI seam end‑to‑end without a GPU or weights.

Registering a `DetectorModel(framework="dummy", active=True)` makes object
detection emit one deterministic `RawDetection` per frame, which then flows
through `ingest_detection` → Event → clip → alarm exactly like a real model.
Used by the AI‑0 tests and for wiring/staging before real weights are deployed.
It never fabricates alarms in production unless an operator explicitly activates
a dummy model row.
"""
from .base import Detector, RawDetection


class DummyDetector(Detector):
    task = "object"

    @property
    def name(self):
        return getattr(self.model, "name", "") or "dummy"

    def infer(self, image_bytes, width, height):
        label = "person"
        conf = 0.9
        if self.model is not None:
            classes = self.model.classes or []
            if classes:
                label = classes[0]
            conf = max(conf, float(self.model.min_confidence) + 0.01)
        # A centered box covering the middle of the frame.
        return [RawDetection(label=label, confidence=conf, bbox=[0.4, 0.4, 0.2, 0.2], track_id="dummy-1")]
