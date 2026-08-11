"""
Detector contract for the inference runtime (Phase AI‑0).

A `Detector` is a loaded model that turns one frame into `RawDetection`s. It is
deliberately camera‑agnostic and event‑agnostic: it knows nothing about
`Camera`, `Event`, zones or dedup. The `runner` attaches the camera, maps
labels onto the Phase‑7 `Detection` contract and applies operator controls.

This keeps model code (which changes often and carries heavy, optional deps)
fully decoupled from the VMS core (which must stay stable and dependency‑light).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawDetection:
    """One model output before it becomes an Event."""

    label: str
    confidence: float                       # 0..1
    bbox: list = field(default_factory=list)  # [x, y, w, h] normalized 0..1
    track_id: str = ""
    extra: dict = field(default_factory=dict)  # plate text, distance, class_id, …


class Detector(ABC):
    """
    Base class for every model backend.

    Subclasses set `task` and implement `infer`. `available()` guards optional
    dependencies / missing weights so the runner can fall back safely; it must
    never raise. `warmup()` is an optional hook for a first, latency‑absorbing
    forward pass.
    """

    task = "object"

    def __init__(self, model=None):
        # `model` is a DetectorModel row (or None for a code‑default detector).
        self.model = model

    # -- identity (surfaced on every Event for auditability) ---------------
    @property
    def name(self):
        return getattr(self.model, "name", "") or self.__class__.__name__

    @property
    def version(self):
        return getattr(self.model, "version", "") or ""

    @property
    def device(self):
        return getattr(self.model, "device", "cpu") or "cpu"

    # -- lifecycle ---------------------------------------------------------
    def available(self) -> bool:
        """True when this detector can actually run. Must not raise."""
        return True

    def warmup(self) -> None:
        return None

    @abstractmethod
    def infer(self, image_bytes: bytes, width: int, height: int) -> list:
        """Return a list of `RawDetection` for one JPEG frame."""
        raise NotImplementedError

    def infer_batch(self, frames: list) -> list:
        """
        Run inference on several frames at once. `frames` is a list of
        `(image_bytes, width, height)`; returns a list of `RawDetection` lists,
        one per input, in order. The default is sequential; a GPU backend
        overrides this to run one batched forward pass for throughput (many
        cameras share a card). Kept here so callers can always batch, whether or
        not the backend truly parallelizes.
        """
        return [self.infer(img, w, h) for (img, w, h) in frames]
