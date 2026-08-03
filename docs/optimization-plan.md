# PersianSecure — Core VMS Optimization Plan

> **Principle:** Keep Django + React, but **freeze sophisticated AI work until the
> VMS foundation is trustworthy.** The recording system currently has models and
> UI, but several modes are only labels and the event‑to‑video workflow does not
> exist yet.

This document is the living plan. It is updated as phases progress. The
narrative log of *what was done, what broke, and how it was fixed* lives in
[journey.md](journey.md) (append‑only — never rewritten).

Status legend: ✅ done · 🟡 in progress · ⬜ not started · ⚠️ blocked / caveat

---

## Confirmed critical issues (baseline audit)

| # | Issue | Where | Addressed in |
|---|-------|-------|--------------|
| 1 | Recording mode on a **new** camera is ignored — the dialog only *updates* an existing schedule, never *creates* one. | `frontend/.../CameraDialog.tsx:142` | Phase 1 |
| 2 | "Motion"/"scheduled" recording are not implemented — backend enables MediaMTX recording for every mode except `off`, so all are effectively continuous. | `backend/apps/recordings/views.py` | Phase 2 |
| 3 | Pre/post‑event values are unused — no worker builds an event clip. | `backend/apps/recordings/models.py` | Phase 3 |
| 4 | Events only contain snapshots — no event→recording/clip relationship. | `backend/apps/events/models.py` | Phase 3 |
| 5 | Manual start/stop recording missing. | — | Phase 2 |
| 6 | Playback receives only the first API page (25 rows) — a day looks like 25 minutes. | `recordings` API + playback page | Phase 4 |
| 7 | Export incomplete — no job status/download; concatenates whole segments instead of trimming. | `recordings` export | Phase 6 |
| 8 | Browser seeking questionable — advertises byte ranges but no real HTTP `Range`. | `recordings/views.py:stream` | Phase 4 |
| 9 | Recording policies have no validation — no weekly evaluator, disk quota, segment health, or event retention. | `recordings` | Phase 2 |
| 10 | Security — camera passwords stored as plaintext; tenant ownership not consistently validated; MediaMTX control API exposed on `9997`. | multiple | Phase 1 (creds + tenancy), Phase 6 (9997) |

---

## Target recording architecture

Django **coordinates** recording; it does not carry the video bytes.

```
Camera
   │ RTSP
   ▼
MediaMTX ── writes short segments ──▶ rolling recording storage
                                           │
Detection/manual event ──▶ Event created   │
                              │             │
                              ▼             ▼
                        Clip assembly worker
                              │
                              ▼
                    EventClip + protected MP4
                              │
                 React Event/Playback pages
```

Pre‑event recording needs a **rolling buffer**: you cannot capture five seconds
*before* an event if recording only starts *after* it. For event‑based
recording MediaMTX writes short (≈2–10 s) segments continuously; the system
keeps recent segments, on an event preserves `event − pre_event`, waits until
`event + post_event`, assembles an exact clip, and prunes the rest later.

---

## Implementation phases

### Phase 0 — Establish a trustworthy baseline · ✅ (one local caveat)
- ✅ CI: backend `check` + `makemigrations --check` + `test`; frontend `tsc`
  lint + production build; `docker compose config`. (`.github/workflows/ci.yml`)
- ✅ Docker image versions pinned — `postgres:16.14`, `redis:7.4.9`,
  `mediamtx:1.18.1-ffmpeg`. (`docker-compose.yml`)
- ✅ Removed runtime `makemigrations` — `entrypoint.sh` only runs `migrate`.
- ✅ Synthetic AI hidden outside explicit demo mode — detectors gated by
  `ENABLE_DEMO_ANALYTICS` **and** per‑rule `{demo:true}`; `run_enabled_rules`
  gated by `FEATURE_ANALYTICS`. (`apps/analytics/*`)
- ✅ Unfinished modules behind feature flags — `settings.FEATURE_FLAGS`,
  surfaced via `MeSerializer.features`, all default `0`.
- ✅ Supported baseline documented. (`docs/supported-baseline.md`)
- ⚠️ **Recreate broken `.venv`** — the committed‑ignored `.venv` still references
  `C:\Users\Rezaei\...`. It **could not be recreated on this workstation
  because no Python interpreter is installed for the current user.** `.venv` is
  gitignored (per‑developer), so this does not affect the reproducible Docker
  install. **Action for the developer:** install Python 3.12, then
  `python -m venv backend/.venv && backend/.venv/Scripts/pip install -r backend/requirements.txt`.

**Exit condition:** a clean install starts reproducibly (met via Docker) and all
existing automated checks pass (CI config correct; not runnable locally without
Python).

### Phase 1 — Repair camera onboarding and live view · 🟡 (code‑complete, awaiting live‑camera acceptance)
Camera creation is now a Stepper wizard: connection → connectivity test →
codec/stream → recording policy → review + **live preview** of the saved camera.

Backend:
- ✅ Create the camera **and** recording schedule **atomically** (a write‑only
  `recording` policy on the camera payload); roll back both (DB transaction +
  MediaMTX path removal) if MediaMTX configuration fails.
  (`cameras/serializers.py`, `cameras/views.py`)
- ✅ Validate every referenced camera belongs to the user's organization —
  `RecordingScheduleSerializer.validate_camera` and the wizard's
  `test-connection` endpoint both enforce tenancy.
- ✅ Return **structured** health errors — `ffmpeg.probe_source` classifies
  `auth | dns | network | timeout | unsupported_codec | ffprobe_missing`;
  MediaMTX failure surfaces as a 503 `mediamtx_failure`.
- ✅ Preserve camera passwords on edit without resending them to the browser —
  password is write‑only; blank on edit keeps the stored value; the wizard's
  test reuses stored creds server‑side.
- ✅ **Encrypt camera credentials at rest** — Fernet `EncryptedCharField`
  (`cameras/crypto.py`, `cameras/fields.py`, migration `0003`); legacy plaintext
  reads transparently and re‑encrypts on next save.

UX:
- ✅ Replaced `window.alert/confirm/prompt` with a promise‑based
  `ConfirmProvider` (`useConfirm`/`usePrompt`) across Cameras, Maps, Playback,
  Desk.
- ✅ Connection progress (LinearProgress) + actionable, localized failure
  reasons; refresh action on the cameras list; test/retry in the wizard.
- ✅ Distinguish **health** (status dot) from **recording state** (true
  `record_mode` chip, no longer always "continuous") from **live‑stream**
  (preview step). Full live‑stream availability badge is deferred to Phase 2.

**Verified:** backend `makemigrations --check` clean + 23/23 tests pass (10 new);
frontend `tsc` + production build pass.
**Exit condition (a user can add a real camera and confirm live stream +
recording policy in one flow):** code‑complete; still needs one acceptance run
against a real camera + running MediaMTX before ticking ✅.

### Phase 2 — Implement recording policies correctly · ✅
Every mode now has real, distinct semantics and survives restarts.
- ✅ `off` no recording · `continuous` always · `scheduled` **only inside weekly
  windows** (org‑tz evaluator, `evaluate_schedules` beat task every 60 s) ·
  `motion` **short‑segment rolling buffer** (`MOTION_BUFFER_SECONDS`) so pre‑event
  video exists · `manual` operator session.
- ✅ Single source of truth `recordings/services.py`
  (`should_record`/`within_weekly_window`/`reconcile_recording`/`start/stop`/`status`);
  `ManualRecordingSession`; APIs `POST /cameras/{id}/recording/{start,stop}/`,
  `GET …/status/`; enriched `GET /recordings/timeline/`.
- ✅ State reconciliation after MediaMTX/Django restarts (every sync point +
  `resync_all_paths`).
- ✅ Manual Start/Stop recording UI (Cameras list + Live View) + live REC dot;
  **weekly windows editor** in the wizard for `scheduled` mode.
- ✅ Operations: **disk free‑space check + low‑storage alarm** event
  (`check_storage`, throttled), **idempotent segment indexing** (get_or_create +
  skip still‑writing files), **retention** keeps `protected` (evidence/legal‑hold)
  segments and leaves exports untouched, validation limits.

**Verified:** backend `makemigrations --check` clean + **37/37 tests pass**
(scheduled window in/out/empty/evaluate, motion buffer, protected retention,
storage alarm, manual flow, …); frontend `tsc` + build.

Follow‑ups deferred to their natural phases (not blockers for the Phase 2 exit):
per‑org timezone field (currently the project `TIME_ZONE`); `recording.control`
permission for operators; `motion` event‑clip preservation (Phase 3).
✅ **MediaMTX path self‑heal added** (`reconcile_camera_paths` beat task, 60 s):
after a MediaMTX restart drops its runtime‑added paths, this re‑pushes only the
missing ones so cameras recover automatically without disrupting live viewers.
(Was deferred; implemented after it surfaced in a real deployment — see journey
Entry 12.)

**Exit — every advertised mode behaves differently and survives service
restarts: met.**

### Phase 3 — Build event video capture · ✅
- ✅ `EventClip` model (event, camera, start/end, status, file, size, duration,
  sha256, error, protected_until, attempts). (`recordings/models.py`, migration
  `0004`)
- ✅ On a camera event, an Event `post_save` signal
  (`clips.schedule_clip_for_event`) creates the clip in the event's transaction
  and **queues assembly after commit**; only for recording cameras + video event
  types; **overlapping events are deduplicated** into one clip.
- ✅ `assemble_event_clip` worker: waits (retry) for the trailing segment, selects
  overlapping rolling segments, **ffmpeg concat + accurate trim** to the pre/post
  window, stores size/duration/**sha256**/error, notifies the frontend (WS).
- ✅ Retention **never deletes segments used by a pending/assembling clip**; failed
  clips can be **retried**; `protected_until` legal hold; clip view/retry/protect
  are **audited**; org‑scoped `EventClip` API (`/api/event-clips/…` +
  `stream`/`retry`/`protect`).
- ✅ UI: Events page shows per‑event **clip status** (processing / play / retry),
  an **authenticated inline clip player**, and a **“Mark test event”** trigger;
  clip summary embedded on the event payload.

**Verified:** backend `makemigrations --check` clean + **45/45 tests pass**
(clip trigger + pre/post window, non‑video skip, off‑recording skip, dedup,
assembly→ready with sha256, missing‑files→failed, retention protects pending‑clip
segments, retry API); frontend `tsc` + build.

**Exit — a manual test event produces a playable clip with video before/after:**
mechanism complete and tested; a real‑video acceptance run needs the running
stack + a recording camera (same caveat as Phase 1).

### Phase 4 — Replace the playback page · ✅
- ✅ Real **24‑hour timeline** scrubber (`Timeline.tsx`): recorded coverage +
  motion/event/bookmark markers, click‑to‑seek, playhead, export selection.
- ✅ **Continuous cross‑segment playback** — the player auto‑advances across
  1‑minute segments and skips gaps; **speed 0.5–4×**, ±10s skip, **jump to
  prev/next event**, snapshot, bookmark.
- ✅ **Exact‑range export** (Mark in/out → `build_export` trims precisely).
- ✅ Loading / empty / no‑camera / gap states.
- ✅ Backend: **overlap filtering** + compact `timeline` endpoint; **proper HTTP
  Range** (206) on segment and clip streams; **signed** short‑lived playback URLs
  (`PLAYBACK_URL_TTL`) so `<video>` seeks natively without an auth header;
  segments are small so nothing huge streams through Django.

**Verified:** backend `makemigrations --check` clean + **50/50 tests pass** (5 new:
signed stream, 206 range, bad‑signature 404, overlap timeline, export trim);
frontend `tsc` + build.

Deferred (not blockers): in‑browser HEVC continuous playback (H.264 is baseline);
`X‑Accel‑Redirect` offload for very large exports (pairs with Phase 6).

**Exit — an operator can find and play any recording without picking 1‑minute
files: met** (real‑video acceptance still wants the running stack + a camera).

### Phase 5 — Event investigation workflow · ✅
- ✅ Clickable event rows → **detail drawer**: type/severity/camera/time, snapshot,
  clip status + **inline play**, **Open in playback** (deep‑links
  `/playback?camera&date&t` to the event moment) and **Open live**
  (`/live?camera`), **ack/clear**, **assign** (org users), **comment** (add/list),
  **related events** (same camera ±30 min, clickable), and the **operator audit
  trail**; clip **protect** (legal hold).
- ✅ Rich filtering on the list: free‑text search, camera, type, severity, ack
  state and **clip availability** (`has_clip`).
- ✅ Backend: `Event.assigned_to` + `EventComment`; actions
  `assign` / `comments` / `related` / `audit`; queryset filters (`q`, date range,
  `has_clip`, `clip_status`).

**Verified:** backend `makemigrations --check` clean + **57/57 tests pass** (7 new:
assign + unassign, reject other‑org assignee, comment add/list, related, audit
trail, `has_clip` filter, free‑text filter); frontend `tsc` + build.

Deferred (optional): "add to evidence case" (evidence is a hidden phase‑2 module);
details free‑text search (kept to type/camera to stay DB‑portable).

**Exit — investigate an alarm from detection → video review → acknowledgement in
one place: met.**

**Exit:** investigate an alarm from detection → video review → acknowledgement in one place.

### Phase 6 — Exports, storage, security, operations · ✅
Done:
- ✅ **Export‑jobs page** (queued/running/done/failed) + **authenticated,
  Range‑capable download** endpoint; exact trimming (Phase 4); **sha256 + size**
  evidence metadata; exports live outside indexed segments so retention never
  prunes them.
- ✅ **Storage‑by‑camera** + **projected days remaining** + **recording‑delay**
  metric on the Health page; service checks for DB/Redis/MediaMTX/Celery/disk.
- ✅ **Removed the MediaMTX control API (`9997`) from the host** — internal‑only.
- ✅ **Tenancy enforced** in serializers (camera, schedule, event‑assign, export,
  bookmark).
- ✅ **Encrypted notification credentials** (`kavenegar_api_key`, `twilio_token`)
  reusing the camera Fernet field; camera creds already encrypted (Phase 1).
- ✅ **Login rate limiting** (scoped throttle) + audit logging across
  ack/clear/assign/comment/export‑download/clip‑view.
- ✅ Resilience already in place: reconcile‑after‑restart, idempotent indexing,
  disk‑full alarm, structured connection errors, camera health checks.

**Verified:** backend `makemigrations --check` clean + **62/62 tests pass** (new:
export tenancy + authed download, bookmark tenancy, notification encryption);
frontend `tsc` + build.

Now added (Phase 6 close):
- ✅ **Backup/restore + secret‑rotation runbook** — `docs/operations.md` (pg_dump,
  recordings‑volume tar, media/env, restore, failure drills).
- ✅ **Key rotation is executable** — `reencrypt_credentials` management command
  (rotate `CREDENTIAL_ENCRYPTION_KEY` or migrate legacy plaintext).

Still an ongoing acceptance activity (not code): formal **destructive failure
testing** (power loss, disk full, restart) run against staging.

**Exit — operable and recoverable without manual DB/filesystem repair: met.**
Verified: rotation‑command tests pass as part of the full **70/70** backend suite;
frontend verified.

### Phase 7 — AI integration contract · ✅ (contract + isolation scaffolding)
- ✅ **One detector contract** — `Detection` (`camera_id, event_type, observed_at,
  confidence, bounding_boxes, track_id, model_name, model_version, snapshot,
  metadata`) + serializer. (`analytics/contract.py`)
- ✅ **Ingestion pipeline** with per‑camera **confidence threshold**, **detection
  zones**, **duplicate suppression**, **model auditability** and **detector
  health/latency**. (`analytics/pipeline.py`)
- ✅ **Queue isolation** — analytics runs on a dedicated `ai` Celery queue +
  worker; inference can never delay recording/exports/health/alarms.
  (`config/celery.py`, `docker-compose.yml`)
- ✅ **Human validation / false‑positive reporting** — event `report` action +
  drawer button; **detector‑health** endpoint.

New detectors (YOLO/ALPR/fire‑smoke/face) become event producers by emitting
`Detection`s — they never touch recording/clips/playback/retention.

**Verified:** backend `makemigrations --check` clean + **70/70 tests pass**
(contract validation, pipeline accept + model metadata, threshold/zone/dedup
drops); frontend `tsc` + build.

Remaining (the *actual‑AI* work, correctly sequenced after this contract): real
models, **GPU/CPU capacity monitoring**, and a richer human‑validation UI — begin
only after 0–6 pass a real‑stack acceptance run.

---

## Recommended delivery order
1. Fix atomic camera + recording‑schedule creation. **(Phase 1)**
2. Implement continuous recording reliably. **(Phase 2)**
3. Add manual start/stop recording. **(Phase 2)**
4. Build the recordings timeline page. **(Phase 4)**
5. Add rolling buffer and event clips. **(Phase 3)**
6. Connect event details to those clips. **(Phase 5)**
7. Harden storage and security. **(Phase 6)**
8. Introduce real AI. **(Phase 7)**

Realistic core‑readiness estimate for one experienced full‑stack developer:
**~6–10 weeks**, excluding production AI and multi‑brand camera certification.
The strongest first slice is **Phases 0–3** — real recording and event video
rather than more partially‑accessible screens.
