# PersianSecure — AI / Computer-Vision Implementation Plan

**Status of the foundation:** Phases 0–7 are done and verified (71 backend tests
green, frontend builds, recording/clips/playback/events all working live on real
cameras). Phase 7 already delivered the **detector contract**, the **ingestion
pipeline** (threshold / zone / dedup / model auditability), **queue isolation**
(a dedicated `ai` Celery queue + worker), a **detector-health endpoint** and
**false-positive reporting**. So the VMS core is trustworthy and AI plugs into a
clean, pre-built seam — exactly the sequencing the master plan required.

This document is the detailed plan for the **actual AI**: real models, real-time
inference, and everything around them. It is written to be executed by one or two
engineers over roughly **8–14 weeks** (excluding data collection and per-model
accuracy tuning, which run in parallel and never truly "finish").

---

## 0. Design principles (non-negotiable)

1. **AI must never degrade the VMS.** Inference runs in its own process/queue and,
   ideally, its own machine/GPU. If the AI stack dies, recording, playback,
   exports, health and alarms keep working. (Already enforced by the `ai` queue.)
2. **Detectors are pure event producers.** A model only emits `Detection`s to
   `ingest_detection`; it never touches recording, clips, playback or retention.
   This is the whole point of the Phase-7 contract.
3. **Every detection is auditable.** model name + version + confidence + boxes are
   stored on the event, so any alarm can be traced to a specific model build.
4. **Human-in-the-loop from day one.** Confidence thresholds, detection zones,
   duplicate suppression and false-positive reporting exist before the first model
   ships, so operators are never buried in noise.
5. **Iran-specific reality.** License plates are **Iranian/Persian** (needs a
   plate model trained/tuned for IR plates, not generic OpenALPR US/EU). Face
   recognition is **legally sensitive** — treat it as opt-in, access-controlled,
   and auditable, and confirm the deployment's legal basis before enabling it.

---

## 1. Target architecture

```
                 RTSP (H.264)
   Cameras ───────────────────► MediaMTX ──► live (WebRTC/HLS) + recording (fMP4)
      │                              │
      │  (a) direct RTSP pull        │
      ▼                              ▼
  ┌─────────────────────────┐   recording volume ──► index ──► Recording rows
  │  Inference Worker(s)     │
  │  • decode @ N fps        │        Event ◄── ingest_detection ◄── Detection(s)
  │  • pre-process / batch   │          │            (threshold/zone/dedup)
  │  • GPU model(s)          │          ▼
  │  • tracker (track_id)    │      EventClip (pre/post video) + alarm feed + WS
  │  • emit Detections ──────┼──────────┘
  └─────────────────────────┘          │
        │  metrics                       ▼
        ▼                        React: alarms, investigation drawer,
  Detector health / GPU monitor       playback, exports, evidence
```

Two clean integration points already exist:

- **Input:** the inference worker builds the camera's RTSP URL with the existing
  `media_client.build_source_url(camera)` (credentials are decrypted transparently).
- **Output:** the worker calls `apps.analytics.pipeline.ingest_detection(Detection,
  rule=…, snapshot=…, latency_ms=…)`. Everything downstream (event → clip → alarm →
  investigation → export → evidence) is already built and tested.

---

## 2. Frame acquisition — the make-or-break decision

Real-time CV needs frames at a controlled rate; the current analytics grabs one
JPEG every ~20 s via ffmpeg, which is fine for coarse motion but not for detection.

**Chosen approach: a dedicated decode-inference worker per camera (or per small
group), decoding directly from RTSP at a controlled FPS.**

- Open the camera's RTSP once per worker (H.264, TCP), decode with
  **PyAV / GStreamer / NVDEC** (hardware decode on GPU if available).
- **Sample smartly:** run detection at **3–8 fps** (configurable per camera), or
  **keyframe-only + motion-gated** to save compute — full 25 fps is wasteful and
  unnecessary for alarms. Motion-gating (only run the model when the cheap
  frame-diff sees activity) can cut GPU load 5–10×.
- **Downscale** to the model's input (e.g. 640×640 for YOLO) — never run detection
  at 1080p.
- **Batch across cameras** on the GPU (e.g. 8–16 frames per forward pass) for
  throughput.

Rejected alternatives (documented so they aren't re-litigated):
- *Re-using MediaMTX's decoded stream:* MediaMTX doesn't expose raw frames.
- *Running CV inside MediaMTX:* couples inference to the media server — violates
  principle #1.
- *Decoding the recorded fMP4 segments:* adds latency (segment must finish first);
  fine for **retrospective/forensic** analysis (a nice AI-6 add-on) but not for
  live alarms.

---

## 3. Model serving & hardware

| Concern | Recommendation |
|---|---|
| **GPU** | One NVIDIA GPU (e.g. RTX 4060/4070/A2000+) handles ~10–25 cameras at 5 fps with a small YOLO. Scale by adding GPUs/workers. CPU-only is possible for a few cameras with a nano model but not recommended for production. |
| **Docker GPU** | `nvidia-container-toolkit`; add a GPU-enabled inference service to `docker-compose` (`deploy.resources.reservations.devices` / `--gpus`). Keep it a **separate service** from the VMS. |
| **Runtime** | **ONNX Runtime** or **TensorRT** for latency; optionally **NVIDIA Triton** to serve multiple models with dynamic batching. Start simple (ONNX Runtime in a Python worker), move to Triton when camera count grows. |
| **Frameworks** | Ultralytics YOLO (v8/v11) for detection; ByteTrack for tracking; ONNX export for portability. |
| **Model storage** | A `models/` volume + a **model registry** row (name, version, path, sha256, input size, classes, metrics). Never hot-swap a model without a version bump (auditability). |

---

## 4. Data model additions (beyond the Phase-7 contract)

Add under a new `apps/ai` app (or extend `analytics`):

- **`DetectorModel`** — `name, task(object|alpr|fire|face), version, framework,
  path, sha256, input_w, input_h, classes(json), active, metrics(json), created_at`.
  The registry; enables versioning, rollback and audit.
- **`DetectorConfig`** (per camera + task) — `camera, task, enabled, model(FK),
  fps, min_confidence, zones(json polygons), classes_filter, dedup_seconds,
  schedule(json)`. This is what the inference worker reads; extends today's
  `AnalyticsRule.config`.
- **`Detection`** (persisted result, optional) — the contract fields + `event(FK),
  track_id, model(FK), false_positive, validated, validated_by`. Lets you build
  the training/feedback loop and per-model accuracy stats.
- **`TrackedObject`** (optional, AI-5) — `camera, track_id, first_seen, last_seen,
  label, path(json)`; for tracking, tripwire-by-direction, dwell time, counting.
- **Face (AI-4, gated):** `FaceGallery`, `FaceIdentity(name, consent, images)`,
  `FaceEmbedding(vector)`, `FaceMatch(event, identity, distance)`. Store
  **embeddings**, not raw galleries, and access-control hard.

All detection-produced events already carry `model_name/model_version/confidence/
bounding_boxes/track_id` in `Event.details` (Phase 7) — the models above make it
queryable and support retraining.

---

## 5. Phased rollout

### AI-0 — Inference infrastructure (foundation) · ~1.5–2 wk · 🟡 IN PROGRESS
The plumbing every model reuses. **No model accuracy work yet.**

> **Landed so far (slice 1, 84/84 tests green):**
> - `DetectorModel` **registry** (`apps/analytics/models.py` + migration `0003`) —
>   versioned, auditable model rows (task, framework, path, sha256, input size,
>   class map, thresholds, device, active, metrics) + admin.
> - **Inference runtime** `apps/analytics/inference/`: `Detector` ABC +
>   `RawDetection`; pure-Python `geometry` (IoU / per-class NMS / letterbox map,
>   unit-tested); `DummyDetector` (end-to-end proof, no GPU); `YoloOnnxDetector`
>   (real YOLOv8/v11 ONNX decode, **optional** numpy/onnxruntime, graceful
>   `available()`); `registry` (resolve+cache active model, GPU/CPU snapshot);
>   `runner` (frame → detector → **`ingest_detection`** with the Phase-7
>   threshold/zone/dedup/audit/health controls).
> - `object_worker` now **prefers a real active model** and falls back to the
>   legacy heuristic/demo path only when none is active.
> - Detector-health endpoint extended with **hardware (GPU/CPU) snapshot** +
>   active-model list.
> - **GPU inference service** in compose (`--profile gpu`, opt-in, inert by
>   default) + `models/` weights dir (git-ignored).
>
> **Landed (slice 2 — continuous decode + tracking, 98/98 tests green):**
> - **Continuous RTSP decode loop** (`inference/frames.py` + `loop.py` +
>   `manage.py run_inference`): one ffmpeg per camera → MJPEG at controlled **fps**
>   → **motion-gate** (`gate.py`, skips static frames) → model → **IoU tracker**
>   (`tracker.py`, stable `track_id` for real dedup/direction) → `ingest_detection`.
>   Per-camera worker threads with reconnect/backoff; `--list` plan mode.
> - **`Dockerfile.gpu`** (numpy + onnxruntime; `--build-arg ORT_PACKAGE=onnxruntime-gpu`
>   for CUDA) — **builds clean**; compose `inference-worker` now runs `run_inference`.
> - **`manage.py register_detector_model`** — register/activate a versioned model
>   from a local weights file (sha256), one active model per task (clean rollback).
> - Runner refactored so the per-snapshot celery path and the continuous loop share
>   one `process_detections` core.
>
> **Still to do in AI-0/AI-1:** download a real YOLOv8 `.onnx` into `./models`,
> register it (`register_detector_model --device cuda`), and validate detections on
> one live camera; optional frame **batching** across cameras for GPU throughput.
- GPU-enabled `inference-worker` service (separate from VMS), `nvidia-container-toolkit`.
- **Frame pipeline:** RTSP decode (PyAV/NVDEC) → fps control → motion-gate →
  resize → batch. One worker manages a configurable set of cameras.
- **Model runner** abstraction (load ONNX/TensorRT, warm-up, batched infer).
- **`DetectorModel` registry** + `DetectorConfig` + admin/API to manage them.
- Wire the runner's output to the existing `ingest_detection` (nothing downstream
  changes).
- **Detector health**: extend the existing `/analytics/detectors/health` with GPU
  util, memory, fps, queue depth, per-model latency (p50/p95).
- **Backpressure**: if the GPU can't keep up, drop frames (never queue unbounded);
  emit a health alarm.
**Exit:** a dummy/passthrough model runs end-to-end, produces events + clips, and
GPU/latency metrics show on the Health page — with the VMS totally unaffected.

### AI-1 — Object detection (persons & vehicles) · ~1.5–2 wk · 🟡 IN PROGRESS
The highest-value first model.

> **Landed:** continuous decode + motion-gate + **IoU tracking** (stable
> `track_id`), real YOLO ONNX decode (graceful), class filter + zones via the
> Phase-7 controls, and **cross-camera batching capability** (`Detector.infer_batch`
> + batched YOLO tensor path + `batching.py` collector/grouper, tested).
> **YOLO11m placed + registered + validated:** exported to `models/yolo11m.onnx`
> (opset 20, dynamic batch), registered as active `DetectorModel #1`, and confirmed
> on the **live cameras** (parking → 2×car+1×motorbike; sales → person+office items;
> etc.). A numpy-float32 JSON-serialization bug in the decoder was caught by this
> validation and fixed. **Remaining:** run an onnxruntime worker (GPU `--profile gpu`
> or a CPU inference worker) so it runs continuously on the streams; wire the batch
> scheduler thread for many-cameras-per-GPU.
- YOLO (v8/v11) COCO or a fine-tuned subset (person, car, truck, bus, motorcycle,
  bicycle). ONNX/TensorRT.
- Per-camera **zones** (already in the contract) and **classes filter**.
- **Tracking** (ByteTrack) → stable `track_id` → real **line-crossing by
  direction** and **loitering/dwell** (replaces the current frame-diff tripwire
  with a proper object-based one).
- Tune per-camera thresholds; validate against a labeled clip set.
**Exit:** person/vehicle alarms with bounding boxes + clips; measurable precision/
recall on a test set; tripwire fires on *objects*, not pixel noise.

### AI-2 — ALPR (Iranian plates) · ~2–3 wk · 🟡 IN PROGRESS
> **Landed (pipeline slice, tested):** `inference/plates.py` — Persian/Arabic digit
> folding, Latin-alias letter mapping, `parse_iranian_plate` (2-digit + Persian
> letter + 3-digit + province validation) + canonical normalization for reliable
> matching; `DummyPlateDetector` + graceful `YoloPlateOcrDetector`; `run_alpr_detection`
> → normalize → **watchlist match (critical alarm)** → `PlateRead` + Event with model
> audit + dedup; `alpr_worker` prefers the active model. **Remaining:** a real
> Iranian-plate detect+OCR `.onnx` (train/fine-tune on site data) wired into
> `YoloPlateOcrDetector.infer`.
- **Detection** of the plate region (a small YOLO) + **OCR** tuned for **Iranian
  plate format** (Persian glyphs, the letter+digits layout). Generic OpenALPR is
  **not** sufficient for IR plates — plan for a plate model trained/fine-tuned on
  Iranian data (collect from the deployed cameras, label, fine-tune).
- Confidence + **plate normalization** + the existing **watchlist match** (already
  built) → critical alarm on a hit.
- Store `PlateRead` (already exists) with model/version + crop image.
**Exit:** reads IR plates on entry/exit cameras at a documented accuracy; watchlist
hit raises a critical alarm with the plate crop + clip.

### AI-3 — Fire / smoke (real model) · ~1.5–2 wk
- Replace the colorimetric heuristic with a trained fire/smoke model (YOLO or a
  CNN classifier), keeping the heuristic as a cheap **pre-filter**.
- Very conservative thresholds + **temporal confirmation** (N consecutive frames)
  to avoid false alarms from sunlight/reflections — a false fire alarm is costly.
- Wire to the existing SMS/voice alarm automation.
**Exit:** fire/smoke detected on test footage with low false-positive rate;
temporal confirmation prevents single-frame false alarms.

### AI-4 — Face detection & recognition (gated, sensitive) · ~2–3 wk
> **Legal/privacy gate.** Confirm the deployment's legal basis before building
> the gallery. Keep it feature-flagged, access-controlled, and fully audited.
- **Detection**: RetinaFace/SCRFD. **Recognition**: ArcFace embeddings + a vector
  index (FAISS) over a consented gallery.
- Watchlist / VIP / blocklist matching → alarm; unknown faces optionally logged.
- Store embeddings (not raw galleries beyond enrollment); strict RBAC + audit on
  every match view.
**Exit:** enrolled identity matched on live video with a tunable distance
threshold; all access audited; disabled by default.

### AI-5 — Analytics intelligence layer · ~2–3 wk · 🟡 STARTED
Turn raw detections into operator value.

> **Landed:** **object-based line-crossing** (`inference/crossing.py` — segment
> intersection + directional `LineCrossingDetector`, unit-tested) wired into the
> live loop: a tracked object crossing a tripwire line raises one **directional**
> critical `tripwire` Event (dedup by `track_id`), replacing the pixel-motion
> tripwire — this is the correct fix for "عبور از خط لابی ۳". **Remaining:** dwell/
> loitering, object-left-behind, occupancy counting, adaptive thresholds, the
> active-learning retrain loop.
- **Duplicate suppression & merging** across frames/cameras (beyond the current
  window dedup) using `track_id` + IoU.
- **Zones & rules per camera**: intrusion, wrong-direction, dwell/loitering,
  object-left-behind, crowd/occupancy counting, queue length.
- **Human validation loop**: the existing false-positive button feeds a labeled
  dataset; periodic **fine-tuning** per site (active learning).
- **Per-camera adaptive thresholds** and time-of-day profiles.
**Exit:** operators tune rules per camera; false-positive reports accumulate into a
retraining set; alarm quality measurably improves.

### AI-6 — Forensic / retrospective AI · ~1–2 wk
Runs on **recorded** footage, not live — no latency pressure.
- Re-run detectors over historical recordings (on-demand or scheduled) for search.
- **Search by attribute**: "red car between 2–4 pm", "person in zone X",
  "plate ABC". Backed by the persisted `Detection` rows + the playback timeline.
- Thumbnail/track summaries on the timeline (event markers already exist).
**Exit:** an operator searches a day of footage by object/plate/attribute and
jumps straight to the matching moment in playback.

### AI-7 — Production ML operations · ongoing
- **Model versioning & rollback** (registry-driven), canary a new model on one
  camera before fleet-wide.
- **Drift & accuracy monitoring**: track precision/recall on a rolling labeled
  sample; alert on regressions.
- **GPU/CPU capacity monitoring** + autoscaling of inference workers by camera
  count/queue depth.
- **Benchmarks**: fps/latency/accuracy per model per GPU, documented.
- **Data governance**: retention of detection crops/embeddings, consent records,
  and export of an audit trail for compliance.
**Exit:** models can be updated, monitored and rolled back safely; capacity is
observable and scalable.

---

## 6. Cross-cutting concerns

- **Performance budget:** target end-to-end alarm latency < ~2 s (frame → event).
  Motion-gating + batching + right-sized models are the levers. Document cameras-
  per-GPU for the chosen model.
- **Accuracy method:** build a **labeled test set per site** (the deployment's own
  cameras) early; every model change is measured against it. Don't trust generic
  benchmarks for these specific scenes.
- **Privacy & legal:** face recognition and plate storage carry obligations —
  consent, retention limits, access control, audit, and a documented legal basis.
  Keep face/ALPR behind feature flags and RBAC.
- **Failure isolation (verified design):** inference OOM/crash → health alarm +
  auto-restart; VMS untouched. Never block `ingest_detection` on a slow model.
- **Config UX:** extend the existing (feature-flagged) Analytics page — per-camera
  model selection, fps, zones (the zone editor pattern exists), thresholds,
  schedule, and a live detector-health panel.

---

## 7. Testing & acceptance (per detector)

For each model: a **labeled clip set** from the real cameras →
precision/recall/false-positive-rate report; a **latency/fps benchmark** on the
target GPU; an **end-to-end test** (detection → event → clip → alarm → investigation
drawer). A detector is not "done" until it has a repeatable accuracy report and an
end-to-end test, mirroring the VMS acceptance discipline.

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| GPU cost/availability | Start with one GPU + motion-gating; CPU-nano fallback for tiny sites; batch aggressively. |
| Iranian plate accuracy | Collect + label site data early; fine-tune; treat generic ALPR as a starting point only. |
| False alarms erode trust | Thresholds + zones + temporal confirmation + dedup + the human-validation loop, all from day one. |
| Face-recognition legal exposure | Feature-flagged, consented gallery, RBAC, audit, documented legal basis. |
| Inference starving the VMS | Separate service/GPU, bounded queues, backpressure, `nice`/thread caps (same lesson as the ffmpeg CPU fix). |
| Model drift over time | Rolling labeled sample + accuracy monitoring + canary + rollback. |

---

## 9. Sequencing & estimate

**Recommended order:** AI-0 → AI-1 (objects) → AI-5 basics (zones/tracking) →
AI-2 (ALPR) → AI-3 (fire/smoke) → AI-6 (forensic search) → AI-4 (face, if legally
cleared) → AI-7 (ongoing ops).

**Rough estimate (one strong CV engineer):** ~**8–14 weeks** to a solid object +
ALPR + fire/smoke deployment with the intelligence layer, excluding continuous
data collection and per-site accuracy tuning. Face recognition and heavy MLOps
extend beyond that.

**Strongest first milestone:** **AI-0 + AI-1** — real object detection with
tracking, producing exactly the same events/clips/investigation flow that already
works, but driven by a real model instead of the frame-diff heuristic. That proves
the whole AI seam end-to-end on one GPU before investing in ALPR/fire/face.

---

*The VMS foundation is verified and ready. Because Phase 7 already built the
contract, the queue isolation and the human-in-the-loop controls, every phase
above is additive — no rework of recording, playback, events or exports is
required.*
