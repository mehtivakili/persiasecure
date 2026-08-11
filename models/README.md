# Model weights (Phase AI-0)

Drop AI model artifacts here (e.g. `yolov8n.onnx`). This directory is bind-mounted
read-only into the GPU inference worker at `/models` (see the `inference-worker`
service in `docker-compose.yml`, `--profile gpu`).

Register each file as a `DetectorModel` row (Django admin → «مدل‌های تشخیص» or the
API) with its `path` (e.g. `/models/yolov8n.onnx`), `task`, `version`, input size,
`classes`, thresholds and `device` (`cpu`/`cuda`), then set `active=True`. The
inference runtime loads the newest active model per task by that row, so every
detection is traceable to an exact, versioned artifact and a bad model can be
rolled back by toggling `active` — no code change.

Weights are intentionally **not** committed to git (see `.gitignore`).
