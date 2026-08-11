"""
Inference runtime (Phase AI‑0).

The bridge between AI models and the trustworthy VMS core. A `Detector`
(dummy, YOLO/ONNX, …) turns a frame into `RawDetection`s; the `runner` maps
those onto the Phase‑7 `Detection` contract and hands them to
`analytics.pipeline.ingest_detection`, which applies the operator controls
(confidence threshold, detection zone, duplicate suppression) and records model
auditability + latency. Detectors never touch recording, clips or playback.

Real model backends (numpy / onnxruntime / CUDA) are optional imports and degrade
gracefully: if the backing library or the weights file is missing, the detector
reports `available() == False` and the runner falls back to the legacy path,
never raising into the alarm loop.
"""
