# PersianSecure — Engineering Journey Log

> **Append‑only.** Never edit or delete earlier entries. New work is added as a
> new dated entry at the **bottom**. Each entry records: what was **asked**, the
> **roadmap**, the **results**, and — for anything that broke — the **error** and
> the **proper approach** used to fix it.
>
> Companion to [optimization-plan.md](optimization-plan.md) (the plan, which *is*
> updated in place as phases progress).

---

## 2026‑08‑02 — Entry 1 · Review plan, verify Phase 0, start Phase 1

### Asked
> "Check if the plan is OK and [that I] implemented Phase 0 OK, then proceed to do
> Phase 1. Update the plan, and create a journey md file that keeps a record of
> what happened and what was done to resolve each error — never delete previous
> records, only add: what I asked, your roadmap, the results, and the proper fix."

### Roadmap
1. Locate the plan (it was not in the repo/memory/git) → user pasted the full
   plan. Assess it for soundness.
2. Verify each Phase 0 item against the actual code.
3. Persist the plan as `docs/optimization-plan.md` and create this journey.
4. Implement Phase 1 (backend onboarding atomicity + security; frontend wizard +
   real dialogs).
5. Verify (frontend `tsc`; backend via Docker/CI since no local Python).

### Plan assessment — is it OK?
**Yes — it is sound and correctly sequenced.** Strengths: it refuses to build AI
on an untrustworthy recording core; the rolling‑buffer insight for pre‑event
capture is correct (you cannot record *before* an event without a continuous
short‑segment buffer); making Django *coordinate* rather than *carry* video is
the right architecture; the exit conditions are concrete and testable. Minor
watch‑outs recorded for later phases: HTTP `Range`/seeking should be delegated to
Nginx `X‑Accel‑Redirect` rather than Django `FileResponse` (Phase 4); event‑clip
dedupe needs a debounce window per camera (Phase 3); credential encryption needs
a **stable, backed‑up key** or recorded credentials become unrecoverable (started
in Phase 1).

### Results — Phase 0 verification
| Item | Verdict | Evidence |
|------|---------|----------|
| CI (backend test/migrations, frontend typecheck, build, compose) | ✅ | `.github/workflows/ci.yml` — `check`, `makemigrations --check`, `test`; `tsc --noEmit`; `vite build`; `docker compose config` |
| Pin Docker images (esp. MediaMTX) | ✅ | `postgres:16.14-alpine3.23`, `redis:7.4.9-alpine`, `mediamtx:1.18.1-ffmpeg` |
| Remove runtime `makemigrations` | ✅ | `backend/entrypoint.sh` runs only `migrate --noinput` |
| Hide synthetic AI outside demo | ✅ | `detectors._demo_enabled` = `ENABLE_DEMO_ANALYTICS` **and** rule `{demo}`; `run_enabled_rules` gated by `FEATURE_ANALYTICS` |
| Unfinished modules behind flags | ✅ | `settings.FEATURE_FLAGS` → `MeSerializer.features`; `.env.example` defaults all `0` |
| Supported baseline documented | ✅ | `docs/supported-baseline.md` |
| Recreate broken `.venv` | ⚠️ blocked | `.venv/pyvenv.cfg` still points to `C:\Users\Rezaei\...` |

**Verdict: Phase 0 is implemented correctly**, with one environment caveat below.

### Error / blocker + proper approach
- **Error:** `.venv` references another Windows user (`C:\Users\Rezaei\...`) and
  could not be recreated — **no Python interpreter is installed for the current
  user** (`python`/`py` resolve only to the Microsoft Store stub; PowerShell finds
  no real 3.12).
- **Impact:** backend tests cannot be run locally on this workstation.
- **Proper approach:** `.venv` is gitignored and per‑developer, so it does **not**
  affect the reproducible Docker install (the real "clean install" path). To close
  it on this machine: install Python 3.12, then
  `python -m venv backend/.venv` and `backend/.venv/Scripts/pip install -r
  backend/requirements.txt`. Backend verification in this session therefore relies
  on the CI definition and (optionally) a one‑off Docker test run; the frontend is
  verified locally with Node 24 (`npm run lint`/`build`).
- **Also noted:** the `.git` directory in the working copy is empty (no HEAD/
  config/history), so there is no git history to diff Phase 0 against; verification
  was done by reading the current tree.

---

## 2026‑08‑02 — Entry 2 · Phase 1 — onboarding atomicity, credential encryption, wizard

### Asked
Proceed with Phase 1 (from Entry 1's approved plan): repair camera onboarding and
live view; update the plan; keep appending to this journey.

### Roadmap
Backend: (1) encrypt camera credentials at rest; (2) create camera + recording
schedule atomically with MediaMTX rollback; (3) close the cross‑tenant schedule
hole; (4) structured connectivity errors. Frontend: (5) promise‑based dialogs to
replace `window.*`; (6) Stepper onboarding wizard with pre‑save test + post‑save
live preview; (7) show the true recording mode. Then verify (frontend `tsc`/build
locally; backend tests via Docker).

### Results — what was done
| Area | Change | Files |
|------|--------|-------|
| Credential encryption | Fernet `EncryptedCharField`; key from `CREDENTIAL_ENCRYPTION_KEY` or derived from `SECRET_KEY`; legacy plaintext auto‑upgrades on save | `cameras/crypto.py`, `cameras/fields.py`, `cameras/models.py`, migration `0003`, `settings.py`, `.env.example`, `requirements.txt` (+`cryptography`) |
| Atomic onboarding | Write‑only `recording` policy on the camera payload → camera + `StreamProfile` + `RecordingSchedule` created in one `transaction.atomic()`; MediaMTX failure rolls back DB **and** removes the path (503 `mediamtx_failure`) | `cameras/serializers.py`, `cameras/views.py` |
| Tenancy | `RecordingScheduleSerializer.validate_camera` + `test-connection` verify the camera is in the caller's org | `recordings/serializers.py`, `cameras/views.py` |
| Structured health | `ffmpeg.probe_source` → `auth/dns/network/timeout/unsupported_codec/ffprobe_missing`; `test` + new `test-connection` (pre‑save, reuses stored creds on edit) | `mediactl/ffmpeg.py`, `cameras/views.py` |
| Dialogs | `ConfirmProvider` (`useConfirm`/`usePrompt`) replaces `window.confirm/prompt` | `components/ConfirmProvider.tsx`, `main.tsx`, `CamerasPage`, `MapsPage`, `PlaybackPage`, `DeskTile` |
| Wizard | 5‑step Stepper (connection→test→stream→recording→review+live preview); progress bar; localized failure reasons; auto‑detected codec | `features/cameras/CameraDialog.tsx` |
| Truth in UI | Cameras list shows the real `record_mode` chip (not always "continuous") + refresh | `CamerasPage.tsx`, `cameras/serializers.py` (`record_mode`) |
| API/i18n | `ProbeResult`, `RecordingPolicy`, `record_mode`, `testConnection`; fa+en keys for steps/probe reasons | `api/types.ts`, `api/endpoints.ts`, `i18n/{fa,en}.json` |

### Verification (actually run)
- **Frontend:** `npm run lint` (`tsc --noEmit`) → clean. `npm run build`
  (`tsc -b && vite build`) → built in ~9 s (pre‑existing >500 kB chunk warning
  only; unrelated to this change).
- **Backend (Docker, `python:3.12-slim`, `settings_test`):**
  `makemigrations --check --dry-run` → **"No changes detected"**;
  `python manage.py test` → **Ran 23 tests … OK** (10 new: encryption at rest +
  legacy plaintext, atomic create, MediaMTX rollback, schedule tenancy, and 5
  probe‑classification cases).

### Errors encountered + proper approach
1. **No local Python (still).** Backend can't be tested on the host.
   *Proper approach used:* ran the suite in a throwaway Docker container mounting
   `backend/` with `--settings=config.settings_test` (in‑memory SQLite, eager
   Celery) — no Postgres/Redis/MediaMTX needed. Repeatable command:
   `docker run --rm -v "<repo>/backend:/app" -w /app python:3.12-slim sh -c "pip install -q -r requirements.txt && python manage.py test --settings=config.settings_test"`.
2. **Hand‑written migration risk.** Phase 0 forbids runtime `makemigrations`, and
   with no local Python I couldn't generate `0003`. *Proper approach:* wrote the
   `AlterField` migration by hand and validated it with `makemigrations --check`
   in Docker — it reported no drift, confirming the migration matches the model.
3. **`tsc` prop‑type friction** passing i18next's `t` into sub‑components and a
   `component="form"` `PaperProps`. *Proper approach:* typed the wizard's step
   `t` prop loosely and cast the form `PaperProps` — narrow, local escape hatches
   rather than weakening the app's types.

### Notes / deferred (tracked in the plan)
- MediaMTX now **blocks** camera creation when it can't be configured (by design —
  "roll back both"). In environments without MediaMTX this returns a clear 503;
  operators must have the media server running to onboard.
- Real **live‑stream availability badge** and motion/scheduled recording semantics
  are Phase 2; the wizard flags motion/scheduled as "records continuously for now".
- Exit condition needs one **acceptance run against a real camera** to tick ✅.

---

## 2026‑08‑02 — Entry 3 · Phase 2 slice — manual record control, recordings visibility, live‑view robustness

### Asked
While running the app the operator reported: (1) "I must be able to **stop/start
recording**" and the record setting buried in the camera‑edit wizard is not
user‑friendly; (2) "I **don't see recorded or currently‑recording videos** in any
page"; (3) Live View **sometimes fails to show a camera and only works after
navigating out and back in**. Also, during the run the seeded demo cameras showed
`path not found` / `no stream on path cam_N`.

### Roadmap
Deliver a Phase‑2 slice: a real manual Start/Stop recording control surfaced on
the Cameras list and Live View (not just the edit dialog); make recordings
actually appear on the Playback page; and make the live player self‑heal. Plus
explain the demo `path not found` (seeding races MediaMTX readiness).

### Results — what was done
| Area | Change | Files |
|------|--------|-------|
| Manual recording | `ManualRecordingSession` model + `services.py` single source of truth (`should_record`/`reconcile_recording`/`start_recording`/`stop_recording`/`recording_status`); `POST /cameras/{id}/recording/start\|stop/`, `GET …/status/` | `recordings/models.py`, `recordings/services.py`, `recordings/migrations/0002`, `cameras/views.py` |
| Reconciliation | Every MediaMTX sync point (camera create/update, schedule save+signal, `resync_all_paths`) now uses the effective state (schedule OR active manual session), so manual recording survives restarts | `cameras/views.py`, `cameras/tasks.py`, `recordings/views.py`, `recordings/signals.py` |
| UI control | Start/Stop **record button** on the Cameras list (per row) **and** Live View (selected camera); live red **REC** indicator; scheduled recording is shown but not manually stoppable | `CamerasPage.tsx`, `LiveViewPage.tsx`, `cameras/serializers.py` (`recording_active`, `manual_recording`) |
| See recordings | Playback now uses the **timeline endpoint (no pagination)** → a whole day of 1‑min segments shows instead of the first 25 (issue #6); auto‑selects the first segment; shows a count | `recordings/views.py` (timeline +`stream_url`/`size`), `PlaybackPage.tsx`, `api/*` |
| Live‑view robustness | `VideoPlayer` **auto‑retries** WebRTC→HLS with backoff (6× / 2.5 s) so on‑demand pull latency self‑heals instead of needing navigate‑away‑and‑back | `components/VideoPlayer.tsx` |
| Tidy | `RecordingSchedule` default ordering (kills the `UnorderedObjectListWarning`) | `recordings/models.py` |

### Verification (actually run)
- **Backend (Docker, `settings_test`):** generated `recordings/0002` via
  `makemigrations`; `makemigrations --check` → "No changes detected";
  `manage.py test` → **Ran 29 tests … OK** (6 new: should_record matrix, manual
  overrides off‑schedule, stop reverts, start/status/stop API flow, viewer
  forbidden). Made the recording tests hermetic (mock MediaMTX in `setUp`) →
  suite dropped from ~31 s to **0.2 s** and the `MediaMTX sync failed` noise is
  gone.
- **Frontend:** `tsc --noEmit` clean; `vite build` OK.

### Errors encountered + proper approach
1. **Demo `path not found` / no live stream.** The seeder (`seed_demo`) calls
   `sync_camera_path` at container start **before MediaMTX is ready**, so the
   path is never registered. *Proper approach (operational):* run
   `docker compose exec backend python manage.py shell -c "from apps.cameras.tasks import resync_all_paths; print(resync_all_paths())"`
   once everything is up. *Proper approach (code, deferred):* have the seeder /
   a startup hook reconcile paths after MediaMTX health is confirmed — noted for
   Phase 2 follow‑up.
2. **Slow, non‑hermetic tests.** Creating a `RecordingSchedule` fires a post_save
   signal that calls MediaMTX; in the test container that DNS‑fails after a 5 s
   timeout ×N. *Proper approach:* patch `media_client.sync_camera_path` in the
   test `setUp` (with `addCleanup`) so recording tests never touch the network.
3. **Hand‑written migration risk (again).** *Proper approach:* generated
   `recordings/0002` inside Docker with `makemigrations`, then confirmed with
   `makemigrations --check` — no drift.

### Notes / deferred
- `scheduled`/`motion` modes still record continuously — the **weekly evaluator**
  and rolling‑buffer/event‑clip work are the rest of Phase 2 / Phase 3.
- Manual start/stop currently requires `camera.manage`; a dedicated
  `recording.control` permission for operators is a small follow‑up.
- Playback is still a segment **list**; the real 24‑hour **timeline scrubber**
  with continuous cross‑segment playback is Phase 4.

---

## 2026‑08‑02 — Entry 4 · Phase 2 completed — schedule evaluator, motion buffer, storage/retention

### Asked
"Do that completely" — finish Phase 2 so every advertised recording mode behaves
differently and survives restarts (not just `off`/`continuous`/`manual`).

### Roadmap
Make `scheduled` obey weekly windows (org‑tz evaluator + editor UI); make `motion`
a real short‑segment rolling buffer; add disk/low‑storage alarms; harden segment
indexing to be idempotent; protect evidence/legal‑hold from retention. Verify with
Docker tests + `tsc`/build.

### Results — what was done
| Area | Change | Files |
|------|--------|-------|
| Scheduled mode | `within_weekly_window` (org‑tz, Persian‑week index `0=Sat`, overnight wrap) + time‑aware `should_record(now)`; `evaluate_schedules` beat task (60 s) toggles MediaMTX as windows open/close | `recordings/services.py`, `recordings/tasks.py`, `config/celery.py` |
| Motion buffer | `motion` records a short‑segment rolling buffer via `MOTION_BUFFER_SECONDS` (default 6 s) — distinct from continuous, and the substrate for Phase 3 event clips | `recordings/services.py`, `config/settings.py`, `.env.example` |
| Storage alarms | `check_storage` beat task (5 min): `shutil.disk_usage` on the recordings volume → throttled critical/warning **storage** Event per org; thresholds `STORAGE_MIN_FREE_GB` / `STORAGE_WARN_FREE_RATIO` | `recordings/tasks.py`, `events/models.py` (+`STORAGE` type), `config/*` |
| Idempotent indexing | `index_recordings` now `get_or_create(file_path=…)` (race‑safe) and skips empty / still‑writing files (mtime < 5 s) | `recordings/tasks.py` |
| Retention | `apply_retention` keeps `protected` segments (evidence / legal hold) and leaves exports untouched; new `Recording.protected` flag | `recordings/models.py`, `recordings/tasks.py` |
| Weekly UI | `WeeklyScheduleEditor` (per‑day time ranges) shown in the wizard for `scheduled` mode; `RecordingPolicy.weekly` on the write path with validation; motion note updated | `features/cameras/WeeklyScheduleEditor.tsx`, `CameraDialog.tsx`, `cameras/serializers.py`, `api/types.ts`, `i18n/*` |

### Verification (actually run)
- **Backend (Docker, `settings_test`):** generated `events/0005_alter_event_type`
  and `recordings/0003_recording_protected`; `makemigrations --check` → "No changes
  detected"; `manage.py test` → **Ran 37 tests … OK** (8 new: scheduled records
  inside window / not outside / empty‑weekly / evaluator reconciles, motion short
  segments, protected‑retention survival, storage alarm critical + ample‑space
  no‑alarm). Suite still ~0.25 s (hermetic).
- **Frontend:** `tsc --noEmit` clean; `vite build` OK.

### Errors encountered + proper approach
- No new blockers. Watch‑item: **`scheduled` semantics changed** — a scheduled
  camera with **no** weekly windows now records **nothing** (previously the old
  code recorded all non‑`off` modes continuously). This is the intended fix; the
  wizard's weekly editor is how windows get defined. Documented so it isn't a
  surprise.
- Timezone: used the project `TIME_ZONE` (Asia/Tehran) as "the org timezone"
  since there is no per‑org tz field yet — noted as a follow‑up.

### Phase 2 exit condition
**Met:** `off` / `continuous` / `scheduled` (window‑bound) / `motion` (short
rolling buffer) / `manual` now behave differently, and recording state is
reconciled to MediaMTX on every change and after restarts.

---

## 2026‑08‑02 — Entry 5 · Phase 3 — event video capture (EventClip)

### Asked
"Start Phase 3" — turn events into playable pre/post‑event clips (the payoff of
the motion rolling buffer).

### Roadmap
`EventClip` model + a post‑commit trigger on Event (gated + deduplicated); an
assembly worker that waits for the trailing segment, concatenates the overlapping
rolling segments and trims exactly to the pre/post window with a checksum;
retention that never prunes segments a pending clip still needs; a clip API
(stream/retry/protect, audited); and an Events UI showing clip status with inline
playback + a test‑event trigger. Verify with Docker tests + `tsc`/build.

### Results — what was done
| Area | Change | Files |
|------|--------|-------|
| Model | `EventClip` (event 1:1, camera, start/end, status, file_path, size, duration, sha256, error, protected_until, attempts) | `recordings/models.py`, migration `0004_eventclip` |
| Trigger | Event `post_save` → `clips.schedule_clip_for_event`: gates on camera + video event type + recording configured; **dedups** overlapping windows; creates clip in the event tx; queues assembly via `transaction.on_commit` with a countdown past the post‑event window | `recordings/clips.py`, `recordings/signals.py` |
| Worker | `assemble_event_clip` (bound, `max_retries=5`): retry until the trailing segment is indexed → concat overlapping segments → `_ffmpeg_trim` (accurate `-ss/-t`, H.264) → size/`_probe_duration`/`_sha256` → `ready`; missing footage → `failed`; `broadcast_event` on completion | `recordings/tasks.py` |
| Retention | `apply_retention` skips segments overlapping any `pending`/`assembling` clip window | `recordings/tasks.py` |
| API | `EventClipViewSet` (org‑scoped) + `stream` (audited) / `retry` / `protect`; clip summary on `EventSerializer`; `Event` queryset `select_related("clip")` | `recordings/{views,serializers,urls,admin}.py`, `events/{serializers,views}.py` |
| UI | Events page clip column (processing / **Play** / **Retry**), **authenticated inline `ClipPlayerDialog`** (fetch with Bearer → blob URL), **“Mark test event”** dialog (raise a manual event on a recording camera), refresh | `features/events/EventsPage.tsx`, `api/{types,endpoints}.ts`, `i18n/*` |

### Verification (actually run)
- **Backend (Docker, `settings_test`):** generated `recordings/0004_eventclip`;
  `makemigrations --check` → "No changes detected"; `manage.py test` → **Ran 45
  tests … OK** (8 new). The logged `clip … failed: بدون قطعهٔ ضبط` and
  `check_storage: critical` lines are the failure/alarm tests exercising those
  paths.
- **Frontend:** `tsc --noEmit` clean; `vite build` OK.

### Errors encountered + proper approach
1. **Reverse OneToOne access on Event.** `event.clip` raises
   `RelatedObjectDoesNotExist` (an `ObjectDoesNotExist`, not `AttributeError`), so
   `getattr(obj, "clip", None)` wouldn't shield it. *Proper approach:* wrap in
   `try/except ObjectDoesNotExist` and `select_related("clip")` to avoid N+1.
2. **Testing assembly without ffmpeg** (the slim test image has none). *Proper
   approach:* factored the ffmpeg call into `_ffmpeg_trim(...)` and patched it in
   the test to write a fake output, then asserted real size/sha256/duration —
   verifying the orchestration without a media stack. Failure path tested via a
   segment row whose file is missing (covers the window but no bytes on disk),
   avoiding celery `retry` in the eager test runner.
3. **App‑load ordering.** `recordings/signals.py` imports `events.models` at
   `ready()`; safe because `cameras`→`recordings`→`events` all have their models
   loaded before any `ready()` runs, and `EventClip.event` uses the string FK
   `"events.Event"` so no import cycle exists at model‑load time.
4. **Authenticated clip playback.** A bare `<video src="/api/…/stream">` sends no
   JWT. *Proper approach:* fetch the clip with the `Authorization` header, wrap in
   a blob URL, and revoke on close.

### Notes / deferred
- Every qualifying event makes a clip (overlap‑deduped). For very chatty motion,
  a per‑camera **debounce window** beyond strict overlap would cut clip volume —
  a Phase 3 tuning follow‑up, not a blocker.
- Clips themselves aren't auto‑pruned yet (kept unless `protected_until`); a clip
  retention policy pairs naturally with Phase 6 storage work.

### Phase 3 exit condition
**Met (mechanism):** a manual "Mark test event" on a recording camera produces an
`EventClip` assembled from the rolling buffer (pre 5s / post 10s), playable inline
with a stored sha256. A real‑video acceptance run needs the running stack + a
recording camera (same caveat as Phase 1).

---

## 2026‑08‑02 — Entry 6 · Phase 4 — timeline playback (scrubber + range + signed URLs)

### Asked
"Start Phase 4" — replace the segment‑list playback page with a real 24‑hour
timeline and continuous playback.

### Roadmap
Decide the continuous‑playback architecture, then: overlap‑filter the timeline,
implement **proper HTTP Range**, hand the browser **signed** per‑segment URLs,
trim exports to the exact range, and build a **timeline scrubber** with
continuous auto‑advance playback, event/bookmark markers, speed, skip, jump‑to‑
event, snapshot, bookmark and range export.

### Decision — how to play continuously
Considered the **MediaMTX playback server** (stitches segments server‑side) but
rejected it as the primary path: I can't verify that feature end‑to‑end here, and
it has a real **timezone‑alignment pitfall** (MediaMTX writes segment filenames in
its container TZ while the indexer makes them aware as `Asia/Tehran`). Chose a
**controllable, testable** design instead: Django serves each small (~1‑min)
segment with correct byte‑range support behind a **short‑lived signed URL**, and
the client plays segments back‑to‑back (**auto‑advance on `ended`**, gap‑skip on
seek). This satisfies every Phase‑4 backend bullet and needs no media‑server
change.

### Results — what was done
| Area | Change | Files |
|------|--------|-------|
| HTTP Range | `ranged_file_response` → real 206 Partial Content (Content‑Range, sliced streaming); used by recording **and** clip streams (fixes issue #8) | `recordings/playback.py`, `recordings/views.py` |
| Signed URLs | `django.core.signing` tokens (`PLAYBACK_URL_TTL`, default 6h) minted by the org‑scoped `timeline`; `stream` accepts a valid `sig` (AllowAny) **or** an authenticated `playback.view` user | `recordings/playback.py`, `recordings/views.py`, `config/settings.py` |
| Overlap timeline | `timeline` now uses **overlap** filtering (`start < before AND (end > after OR end null)`) instead of start‑only, returns signed `stream_url` per segment | `recordings/views.py` |
| Exact export | `build_export` trims to the exact `[start,end]` via `_ffmpeg_trim` (offset/duration, re‑encode) instead of concatenating whole segments (issue #7) | `recordings/tasks.py` |
| Scrubber UI | New `Timeline` bar (coverage + motion/event/bookmark markers, click‑seek, export selection, playhead; forced LTR); `PlaybackPage` rebuilt as a continuous player: auto‑advance across segments, gap‑skip, **speed 0.5–4×**, ±10s skip, **jump prev/next event**, snapshot, bookmark, **Mark in/out → exact‑range export**, loading/empty/gap states | `features/playback/{Timeline,PlaybackPage}.tsx`, `i18n/*` |

### Verification (actually run)
- **Backend (Docker, `settings_test`):** `makemigrations --check` → no changes;
  `manage.py test` → **Ran 50 tests … OK** (5 new: signed full stream, **206
  range** with correct Content‑Range/length/body, bad‑signature 404, overlap
  timeline includes a segment starting before the window + signed url, export
  trims to exact offset/duration).
- **Frontend:** `tsc --noEmit` clean; `vite build` OK.

### Errors encountered + proper approach
1. **301 on the stream URL.** The DRF router route is `…/stream/` (trailing
   slash); my signed URLs and tests omitted it, so `APPEND_SLASH` returned 301.
   *Proper approach:* added the trailing slash to `signed_stream_url` and the clip
   `stream_url` builders (and tests) so the browser is never redirected.
2. **Auth vs. native `<video>` seeking.** A `<video src>` can't send a Bearer
   header, and blob fetching breaks continuous seeking. *Proper approach:*
   **signed URLs** — the timeline (JWT, org‑scoped) mints time‑limited tokens, and
   the stream endpoint validates the signature, so native range/seek works with no
   header. This is the plan's "signed or permission‑checked playback URLs".
3. **RTL vs. a left→right timebar.** *Proper approach:* forced the timeline
   container `dir="ltr"` so 00:00→24:00 maps predictably to x, independent of the
   app's RTL layout.

### Notes / deferred
- HEVC continuous playback in‑browser is still limited (segments are native HEVC);
  H.264 is the supported baseline. On‑the‑fly playback transcoding is a later
  optimization.
- nginx `proxy_buffering` is on for `/api`; fine for ~1‑min segments. For very
  large exports, an `X‑Accel‑Redirect` path (Phase 6) would offload Django.

### Phase 4 exit condition
**Met:** an operator picks a camera + day and plays straight through the day from
any point on the timeline — continuous across 1‑minute segment boundaries, with
seek/speed/skip/jump‑to‑event and exact‑range export — without ever choosing an
individual file. (Real‑video acceptance still wants the running stack + a
recording camera.)

---

## 2026‑08‑02 — Entry 7 · Phase 5 — event investigation workflow

### Asked
"Start Phase 5" — make events clickable and investigable end‑to‑end: detail with
video, ack/comment/assign, related events, audit, and rich filtering.

### Roadmap
Backend: `assigned_to` + `EventComment`; `assign`/`comments`/`related`/`audit`
actions; list filters (search, date range, clip availability). Frontend: a
right‑hand **event detail drawer** wired to all of it, clickable rows, a filter
bar, and deep‑links so the drawer's "Open in playback/live" land on the right
camera + moment. Verify with Docker tests + `tsc`/build.

### Results — what was done
| Area | Change | Files |
|------|--------|-------|
| Model | `Event.assigned_to` + `EventComment` | `events/models.py`, migration `0006` |
| Actions | `assign` (org‑scoped, unassignable), `comments` (GET/POST), `related` (same camera ±30 min), `audit` (AuditLog for the event) | `events/views.py` |
| Filters | `q` (type/camera search), `after`/`before` (ts range), `has_clip`, `clip_status` | `events/views.py` |
| Serializer | `assigned_to(_name)`, `comment_count`; `EventCommentSerializer` | `events/serializers.py` |
| Drawer | `EventDetailDrawer`: header, snapshot, clip play (shared `ClipPlayerDialog`), **Open in playback/live**, ack/clear, assignee select, comments add/list, related list, audit trail, clip **protect** | `features/events/{EventDetailDrawer,ClipPlayerDialog}.tsx` |
| List | Clickable rows → drawer; filter bar (search/camera/type/severity/clip/ack); action buttons `stopPropagation` so they don't open the drawer | `features/events/EventsPage.tsx` |
| Deep‑links | `PlaybackPage` reads `?camera&date&t` (seeks to the event moment); `LiveViewPage` reads `?camera` | `features/playback/PlaybackPage.tsx`, `features/liveview/LiveViewPage.tsx` |
| API/i18n | `assignEvent`, `eventComments`, `addEventComment`, `relatedEvents`, `eventAudit`, `protectEventClip`; extended `events` filters; fa+en keys | `api/{types,endpoints}.ts`, `i18n/*` |

### Verification (actually run)
- **Backend (Docker, `settings_test`):** generated `events/0006`;
  `makemigrations --check` → no changes; `manage.py test` → **Ran 57 tests … OK**
  (7 new investigation tests).
- **Frontend:** `tsc --noEmit` clean; `vite build` OK.

### Errors encountered + proper approach
1. **Row click vs. inline action buttons.** DataGrid `onRowClick` fires even when
   an action IconButton is clicked. *Proper approach:* `e.stopPropagation()` in the
   ack/clear/clip button handlers so they act without opening the drawer.
2. **Cross‑tenant assignee.** *Proper approach:* the `assign` action resolves the
   user from an org‑scoped queryset and 400s on a stranger — same tenancy rule as
   the rest of the app.
3. **Free‑text over a JSONField.** `details__icontains` isn't portable across
   sqlite/Postgres. *Proper approach:* limited `q` to `type` + camera name (both
   plain text); details/comment full‑text is a later, DB‑aware follow‑up.

### Notes / deferred
- "Add to evidence case" omitted (evidence is a hidden phase‑2 module); the drawer
  exposes protect/open‑in‑playback instead. Details full‑text search deferred.

### Phase 5 exit condition
**Met:** from the Events list an operator opens an alarm, watches its clip (or
jumps into playback at the exact time), acknowledges/clears, assigns an owner,
comments, reviews related events and the audit trail — all without leaving the
page.

---

## 2026‑08‑02 — Entry 8 · Phase 6 — exports, storage, security & operations

### Asked
"Start Phase 6" — exports page + authed downloads + checksums, storage‑by‑camera,
remove the MediaMTX control API from the host, enforce tenancy, encrypt
notification creds, rate limiting, health metrics.

### Roadmap
Do the concrete, testable security/exports/storage items; be explicit that
backup/restore + secret rotation + destructive failure testing are operational
runbooks, not app code, and won't be faked.

### Results — what was done
| Area | Change | Files |
|------|--------|-------|
| Security | **Removed `9997` (MediaMTX control API) from the host**; **login rate limit** (scoped throttle, `LOGIN_THROTTLE_RATE`); **encrypted** `NotificationSettings.kavenegar_api_key`/`twilio_token` (reused the camera Fernet field); **tenancy** validators on `ExportJob` + `Bookmark` cameras | `docker-compose.yml`, `config/settings.py`, `accounts/views.py`, `events/models.py`+`serializers.py`, `recordings/serializers.py`, migrations `events/0007` |
| Exports | `ExportJob.size`/`sha256`; `build_export` computes them; **authed, Range‑capable `download`** action; `download_url` on the serializer; **Exports page** (states + size + sha256 + download, polling) + route + nav | `recordings/{models,serializers,views,tasks}.py`, migration `recordings/0005`, `features/exports/ExportsPage.tsx`, `App.tsx`, `AppLayout.tsx`, `api/*` |
| Storage/health | `system/health` now returns **storage‑by‑camera**, **projected days remaining** and **recording‑delay**; Health page renders them | `dashboard/health.py`, `features/health/HealthPage.tsx` |

### Verification (actually run)
- **Backend (Docker, `settings_test`):** generated `events/0007` +
  `recordings/0005`; `makemigrations --check` → no changes; `manage.py test` →
  **Ran 62 tests … OK** (5 new: export tenancy + authed download done/pending,
  bookmark tenancy, notification‑credential encryption at rest).
- **Frontend:** `tsc --noEmit` clean; `vite build` OK.

### Errors encountered + proper approach
1. **Login throttle would cascade‑fail the test suite.** Almost every
   `APITestCase.setUp` logs in from one IP; a 10/min throttle trips after test 10.
   *Proper approach:* disabled the `login` throttle rate in `settings_test`
   (`DEFAULT_THROTTLE_RATES = {"login": None}`) — production keeps the limit, tests
   don't self‑DoS. (So the throttle itself is config‑verified, not unit‑tested.)
2. **Where to encrypt.** Reused the existing `cameras.fields.EncryptedCharField`
   for notification secrets rather than a second mechanism — one Fernet key, one
   code path; `events.models` already imports `cameras` so no new coupling.

### Notes / deferred (honest scope)
- **Backup/restore** (Postgres + recordings volume) and **secret rotation** are
  **operational runbooks**, not application code — not implemented here on purpose
  (faking them would be worse than naming them). Same for a formal **destructive
  failure test suite** (power loss, disk full, restart), though the app already
  reconciles recording state after restarts, indexes idempotently, alarms on low
  disk, and reports structured connection errors.
- The `9997` change means the media server can no longer be hit from the host — the
  backend reaches it internally; nothing else should.

### Phase 6 exit condition
**Met for day‑to‑day operation + restart recovery.** Full disaster recovery
(a backup/restore runbook) is the one remaining operational piece before this can
be ticked ✅ outright.

---

## 2026‑08‑03 — Entry 9 · Phase 6 closed — ops runbook + key rotation

### Asked
"Do the backup/restore + secret‑rotation runbook to close Phase 6, then start
Phase 7."

### Results
- **`docs/operations.md`** — real backup (`pg_dump` | volume tar | media/env),
  restore, and **secret‑rotation** procedures for this Compose stack, plus a
  failure‑drill checklist. Emphasises that **`CREDENTIAL_ENCRYPTION_KEY` must be
  backed up** or encrypted credentials are unrecoverable.
- **`reencrypt_credentials` management command** — makes key rotation *real*:
  decrypts each camera password + notification secret with the old key and
  re‑encrypts with the current one (also migrates legacy plaintext). Uses raw‑SQL
  reads + `QuerySet.update()` so values never pass through the wrong key. Helpers
  `crypto.fernet_from_key` / `crypto.decrypt_with` added.

**Verification:** two command tests written (legacy‑plaintext migrate; old‑key
rotation). ⚠️ **Not yet executed** — Docker Desktop was down at the end of the
session and would not start non‑interactively; run
`docker run --rm -v "<repo>/backend:/app" -w /app python:3.12-slim sh -c "pip install -q -r requirements.txt && python manage.py test --settings=config.settings_test"`
once Docker is up. Frontend unaffected.

### Phase 6 exit condition — now met
Backup/restore + rotation are documented and (rotation) executable, so the system
can be recovered without manual DB/filesystem repair.

---

## 2026‑08‑03 — Entry 10 · Phase 7 — AI detector contract + queue isolation

### Asked
"Start Phase 7" — prepare the AI integration contract (do **not** ship real
models yet; the plan gates that on 0–6 passing end‑to‑end).

### Roadmap
Define one detector contract; ingest detections through operator controls
(threshold/zone/dedup) into the normal Event→clip flow; isolate inference on its
own Celery queue; add detector health + false‑positive reporting.

### Results — what was done
| Area | Change | Files |
|------|--------|-------|
| Contract | `Detection` dataclass + `DetectionSerializer` (camera_id, event_type, confidence, observed_at, bounding_boxes, track_id, model_name/version, snapshot, metadata) | `analytics/contract.py` |
| Pipeline | `ingest_detection`: per‑camera **confidence threshold**, **detection‑zone** (point‑in‑polygon), **duplicate suppression** (per camera+type+track, windowed), model auditability on the Event, and **detector health/latency** recording | `analytics/pipeline.py` |
| Queue isolation | Celery `task_routes` send `apps.analytics.tasks.*` to an **`ai`** queue; core worker runs `-Q celery`, a new **`celery-worker-ai`** runs `-Q ai` — inference can't delay recording/exports/health/alarms | `config/celery.py`, `docker-compose.yml` |
| Monitoring | `GET /api/analytics/detectors/health` (runs, avg latency, last‑seen per model) | `analytics/views.py`+`urls.py` |
| Human‑in‑the‑loop | Event `report` action (`false_positive`/`validated`, auto‑clears confirmed FPs); drawer shows **detected‑by model/confidence** + a **Report false positive** button | `events/views.py`, `features/events/EventDetailDrawer.tsx`, `api/*`, `i18n/*` |

Existing analytics workers are untouched; **new** detectors (YOLO/ALPR/fire‑smoke/
face) become event producers by emitting `Detection`s to `ingest_detection` — they
never need to know how recording/clips/playback/retention work.

**Verification:** pipeline + contract tests written (accept + model metadata,
threshold drop, zone drop, dedup drop, serializer validation). ⚠️ **Backend suite
not yet executed** (Docker down — same as Entry 9). **Frontend verified:**
`tsc --noEmit` clean, `vite build` OK.

### Notes / deferred (the actual‑AI work, post‑contract)
- Real models (YOLO/ALPR/fire‑smoke/face), **GPU/CPU capacity monitoring**, and a
  richer human‑validation UI are the follow‑on once 0–6 pass a real‑stack
  acceptance run — exactly the sequencing the plan prescribes.
- Celery glob routing (`apps.analytics.tasks.*`) is a documented feature but is a
  runtime behavior not covered by unit tests; if a pattern ever fails to match,
  analytics safely falls back to the core queue (no isolation, not broken).

---

## 2026‑08‑03 — Entry 11 · Verification catch‑up (closes Entries 9 & 10)

The backend suite that Entries 9 and 10 flagged as **written but not run** (Docker
Desktop was down) has now been executed: Docker was restarted and

- `makemigrations --check` → **No changes detected**
- `python manage.py test --settings=config.settings_test` → **Ran 70 tests … OK**

This includes the `reencrypt_credentials` rotation tests (legacy‑plaintext migrate
+ old‑key rotation) and the Phase 7 detector‑pipeline/contract tests
(threshold/zone/dedup/accept + serializer validation). **The ⚠️ caveat in Entries
9 and 10 is closed — all eight phases (0–7) are now implemented and verified**
(70/70 backend tests + frontend `tsc`/build). A real‑camera acceptance run remains
the only outstanding sign‑off item.

---

## 2026‑08‑03 — Entry 12 · Field fixes from a real deployment (analytics flag + cameras "offline")

### Asked
Operator, running the app on a real site with 5 LAN cameras (Hikvision‑style,
192.168.100.x): (1) couldn't find where to define a **tripwire / line‑crossing**
rule; (2) all cameras showed **offline / «بدون سیگنال»** in Live View.

### Diagnosis + fix
1. **Tripwire rules not visible → feature flag.** The whole Analytics page (which
   holds the tripwire line editor) is gated by `FEATURE_ANALYTICS`, which was `0`
   (Phase‑0 design: unfinished modules hidden). Set `FEATURE_ANALYTICS=1` in
   `.env`; after `up -d` + a refresh the «تحلیل تصویر» menu + tripwire editor
   appear. (Not a bug — intended gating.)
2. **Cameras offline → MediaMTX lost its paths.** Diagnosed live: the camera
   itself streams fine (`ffmpeg.probe_source` on cam 18 → `ok, h264, 1920×1080`;
   TCP to :554 OK; creds present). But `is_camera_ready` was False because
   **MediaMTX paths are runtime‑added via its API and are dropped when the
   MediaMTX container restarts** (the operator's `up --build` restarted it).
   Nothing re‑pushed them. Immediate fix: `resync_all_paths()` → cam 18 went
   `ready False → True`.
   **Proper fix (closes the long‑standing deferred item):** new
   `reconcile_camera_paths` beat task (every 60 s) re‑pushes **only paths missing
   from MediaMTX config** (`client.path_is_configured`), so it self‑heals after a
   restart **without** touching existing paths / disrupting live viewers.

### Verification
- Live: resync took cam 18 online; `reconcile_camera_paths()` returns `0` when all
  paths already exist (no disruption), and the unit test confirms it re‑pushes
  only the missing camera.
- `apps.cameras` tests pass (17) incl. `ReconcileCameraPathsTests`;
  `makemigrations --check` clean.

### Note for the operator
- The new self‑heal needs the workers reloaded to take effect:
  `docker compose restart backend celery-worker celery-beat` (code is
  volume‑mounted, so no rebuild). After that, a MediaMTX restart recovers cameras
  automatically within ~60 s.
- The bare `/` RTSP path works for these cameras (they stream 1080p H.264), so no
  per‑camera path change is needed.

---

## 2026‑08‑03 — Entry 13 · Field fixes #2 — no event clip + broken playback selection

### Asked
On the real site: (1) tripwire events on «لابی ۳» show **"no clip"** — operator
expects a 5s‑before/after clip saved on each crossing; (2) the **playback timeline
selection is wrong** — clicking selects a "future"/mirrored point and often won't
select the recorded parts at all.

### Diagnosis + fix
1. **No clip = the camera wasn't recording.** The tripwire camera (id 19) had
   `RecordingSchedule.mode = off` and **0 recorded segments**, while its siblings
   were `continuous`. An event clip needs footage from *before* the event, so with
   recording off, `schedule_clip_for_event` correctly created **nothing** (0
   EventClip rows). *Fix:* set camera 19 to `continuous` (reconciled → MediaMTX
   now records it); new crossings will produce clips. Past events can't be
   clipped (no footage existed). *Guard against recurrence:* the analytics rule
   dialog now shows a **warning when the chosen camera isn't recording** ("event
   clips can't be built — enable recording first").
2. **Playback selection mirrored = RTL.** `stylis-plugin-rtl` rewrites physical
   `left`→`right` at build time, so the whole timeline (coverage, markers,
   playhead) rendered **mirrored**, while the click math still measured from the
   left edge → clicks landed on the mirror‑image time (a gap → "won't select").
   *Fix:* position every timeline element with the **logical `insetInlineStart`**
   (which the RTL plugin leaves untouched) inside the `dir="ltr"` box, so time
   flows left→right and `clientX − rect.left` maps correctly. Marker centering
   moved from `translateX(-50%)` to logical `marginInlineStart`.

### Verification
- Live: camera 19 mode now `continuous`, MediaMTX path configured (recording).
- Frontend `tsc` clean + `vite build` OK.

### Apply
- Camera‑19 recording change is live (backend, no rebuild).
- The timeline + warning are frontend changes → rebuild the frontend image:
  `docker compose up -d --build frontend`.

---

## 2026‑08‑03 — Entry 14 · ROOT‑CAUSE bug — recording/event timezone misalignment

### Symptom
On the live site: event clips kept **failing** ("no segment for this window") and
"Open in playback" for tripwire events showed **no footage**, even though the
cameras were recording (files on disk up to the current minute). The playback
timeline showed recorded (blue) coverage ~3.5 h **before** the event markers.

### Root cause
`index_recordings._parse_start` interpreted the MediaMTX segment **filename** time
with `timezone.make_aware(naive, get_current_timezone())` → **Asia/Tehran**. But
the mediamtx container has no `TZ`, so it writes filenames in **UTC**. Result:
a file named `10-16-02` (UTC) was stored as `10:16 Tehran = 06:46 UTC` — **every
recording landed 3.5 h earlier than reality**. Events (`Event.ts`, correct UTC)
therefore never overlapped their own footage → clip assembly's overlap query
found nothing, and the timeline drew coverage 3.5 h off from events. (Several of
the earlier "recording gaps" I chased were partly this misalignment, not only
MediaMTX path loss.)

### Fix
- `_parse_start` now interprets the filename as **UTC**
  (`datetime(..., tzinfo=timezone.utc)`) — the permanent fix.
- Corrected existing data: shifted all **1055** `Recording` rows by **+3:30** so
  their stored times match reality (`start`/`end` via an `F()` update — no
  re‑probe needed).
- Restarted `backend`/`celery-worker`/`celery-beat`/`celery-worker-ai` to load the
  fixed code, and **re‑queued the 18 failed clips** — with recordings now aligned
  to events, they reassemble from the correct segments.

### Verify / apply
- Refresh the Playback page — blue coverage now sits **under** the event markers
  (same times); "Open in playback" lands on real footage.
- Lesson for deployment robustness: pin the mediamtx container to a known TZ (it's
  UTC) — the parser now assumes UTC to match. If a future deployment sets a
  different mediamtx TZ, filenames + parser must agree.

## 2026‑08‑03 — Entry 15 · Readiness sign‑off + AI/computer‑vision implementation plan

### Asked
"یه پلن خیلی خیلی کامل و دقیق بریز برای پیاده‌سازی اون هوش مصنوعی و پردازش تصویری …
فقط قبلش بررسی کن که هیچ ایراد دیگه‌ای باقی نمونده و آماده‌ایم که بریم سراغ قسمت
اصلی کار" — first confirm nothing else is broken, then write a very complete,
precise plan for the AI / image‑processing work.

### Readiness verification (before writing the plan)
- Live diagnostics (throwaway Django script): all 5 cameras `mediamtx_ready=True`;
  event clips `{ready:27, assembling:0, pending:2, failed:0}`; events(24h)=61;
  recordings total=1263 — recording is continuous, no failed clips.
- Backend test suite (throwaway `python:3.12-slim` container): **71/71 pass**,
  `makemigrations --check` = "No changes detected" (timezone fix in `_parse_start`
  and the `-threads 2` ffmpeg change introduced no regressions/migrations).
- Frontend: `tsc` clean, `vite build` OK (~18.5 s).
- Conclusion: no outstanding defects — foundation is ready for the AI phase.

### Delivered
- `docs/ai-plan.md` — the full AI/CV implementation plan. Highlights: it builds on
  the Phase‑7 contract (Detection dataclass, `ingest_detection` threshold/zone/dedup,
  `ai` queue isolation, detector‑health + false‑positive reporting) so every AI
  phase is additive. Covers: target architecture + integration seams (input via
  `media_client.build_source_url`, output via `ingest_detection`); the make‑or‑break
  **frame‑acquisition** decision (dedicated RTSP decode‑inference worker, fps
  control + motion‑gating + batching, with rejected alternatives documented);
  model serving/GPU (ONNX Runtime/TensorRT/Triton, `nvidia-container-toolkit`, a
  separate inference service); new data models (`DetectorModel` registry,
  `DetectorConfig`, persisted `Detection`, tracking, gated face tables); a phased
  rollout **AI‑0…AI‑7** (infra → objects+tracking → analytics rules → Iranian‑plate
  ALPR → fire/smoke → forensic search → gated face recognition → MLOps); cross‑cutting
  performance/accuracy/privacy/failure‑isolation concerns; per‑detector testing &
  acceptance; risks & mitigations; ~8–14 wk estimate with AI‑0+AI‑1 as the first
  end‑to‑end milestone.
- Non‑negotiables carried over: AI never degrades the VMS (separate service/queue),
  detectors are pure event producers, everything auditable, human‑in‑the‑loop from
  day one, and Iran‑specific realities (Persian plates need a tuned model; face
  recognition is legally sensitive and stays feature‑flagged/RBAC'd).

## 2026‑08‑03 — Entry 16 · AI‑0 slice 1 — inference foundation (started building)

### Asked
"start it" — begin implementing the AI plan.

### Roadmap for this slice
Build the AI‑0 foundation that every model reuses, fully testable on CPU with a
dummy model, routed through the existing Phase‑7 controls — no GPU/real weights
required yet. Real continuous‑decode loop + a downloaded YOLO model come next.

### Done
- **Registry:** `DetectorModel` (`apps/analytics/models.py`, migration
  `0003_detectormodel`) — versioned/auditable model rows (task, framework, path,
  sha256, input size, class map, min_confidence/iou, device cpu|cuda, active,
  metrics) + admin (`active` inline‑editable). `active_for(task)` helper.
- **Inference runtime** `apps/analytics/inference/`:
  - `base.py` — `Detector` ABC + `RawDetection` (camera/event‑agnostic).
  - `geometry.py` — pure‑Python IoU / per‑class NMS / letterbox map (unit‑tested,
    no numpy) shared by all backends.
  - `dummy.py` — `DummyDetector` (deterministic, proves the seam end‑to‑end).
  - `yolo.py` — `YoloOnnxDetector`: standard YOLOv8/v11 ONNX decode (letterbox →
    argmax → unletterbox → NMS). numpy/onnxruntime are **optional imports**;
    missing deps or weights ⇒ `available()==False` (never raises into the alarm
    loop). CUDA provider when `device=cuda`.
  - `registry.py` — resolves newest active `DetectorModel`→`Detector`, caches by
    id+`updated_at` (reloads on change); `hardware_snapshot()` (os load avg +
    `nvidia-smi`, best‑effort, never raises).
  - `runner.py` — `run_object_detection(rule)`: frame → detector → `Detection` →
    `ingest_detection` (Phase‑7 threshold/zone/dedup/audit/health). Returns
    `NO_MODEL` sentinel so the caller can fall back. A detector crash is caught
    and logged, never propagated.
- **Wiring:** `object_worker` now prefers a real active model via the runner and
  only falls back to the legacy OpenCV‑DNN/demo detector when none is active.
- **Health API:** `detectors/health` now returns `{detectors, hardware,
  active_models}` (GPU/CPU snapshot + which model is live on which device). No
  frontend/test consumed the old flat shape, so safe.
- **Deploy artifact:** opt‑in `inference-worker` compose service
  (`--profile gpu`, nvidia device reservation, onnxruntime‑gpu) — inert by
  default so the normal stack is unchanged; `models/` weights dir + README,
  git‑ignored.

### Verify
- Throwaway `python:3.12-slim`: `makemigrations --check` = clean; full suite
  **84/84 OK** (was 71 → +13 inference tests: geometry IoU/NMS/letterbox, registry
  resolve+cache+reload, dummy end‑to‑end → Event, confidence‑threshold + class
  filter suppression, YOLO graceful‑unavailable).
- Design guarantee held: no numpy/onnxruntime added to `requirements.txt`, so the
  core image stays light; the real backend’s heavy deps live only in the opt‑in
  GPU service.

### Next
Continuous RTSP decode loop (fps + motion‑gate + batch), a baked `Dockerfile.gpu`,
then download + register a real YOLO `.onnx` and validate on one live camera (AI‑1).

## 2026‑08‑03 — Entry 17 · AI‑1 slice — continuous decode + tracking + GPU image

### Asked
"ادامه بده به بهترین روشی که خودت فک میکنی نیازه" — continue however is best.

### Roadmap
Upgrade from per‑snapshot sampling (one frame / 20 s) to a real‑time continuous
decode loop with fps control + motion‑gating + object tracking, and make the GPU
deployment path real — all with unit‑tested pure helpers so it verifies on CPU.

### Done
- **Runner refactor** (`inference/runner.py`): split into `infer_frame` (timed,
  crash‑safe) + `process_detections` (class filter → `Detection` → `ingest_detection`)
  shared by both the celery per‑snapshot path and the continuous loop.
- **Motion gate** (`inference/gate.py`): Pillow luma frame‑diff on a 64×36
  downsample; skips inference on static frames (the biggest multi‑camera GPU
  saving). First frame passes; decode error fails open.
- **IoU tracker** (`inference/tracker.py`): greedy IoU association → stable
  `track_id` (ByteTrack‑style, no Kalman), age‑out. Stable ids make the Phase‑7
  track‑based dedup real and unlock direction/dwell later.
- **Frame source** (`inference/frames.py`): one ffmpeg per camera
  (`image2pipe`/mjpeg) at controlled fps+scale; pure‑Python `extract_jpeg_frames`
  SOI/EOI splitter (unit‑tested) + `RtspFrameSource` context manager.
- **Continuous loop** (`inference/loop.py` + `manage.py run_inference`):
  `plan()` picks eligible object rules (feature on + active model + enabled cams);
  `CameraWorker` thread per camera (decode→gate→infer→track→ingest, reconnect
  backoff); `InferenceService` orchestrates + SIGTERM‑clean. `--list` dry‑run.
- **Model registration** (`manage.py register_detector_model`): register a
  versioned model from a local weights path (computes sha256); `--activate`
  enforces one active model per task (clean rollback). Renamed flag to
  `--model-version` (Django reserves `--version` on every command — first test run
  caught the argparse conflict).
- **`backend/Dockerfile.gpu`**: base image + numpy + onnxruntime
  (`--build-arg ORT_PACKAGE=onnxruntime-gpu` for CUDA); compose `inference-worker`
  builds from it and runs `run_inference` (still `--profile gpu`, opt‑in).

### Verify
- Throwaway `python:3.12-slim`: `makemigrations --check` clean; full suite
  **98/98 OK** (84 → +14: mjpeg splitter incl. partial‑frame remainder, motion
  gate pass/skip/fail‑open, tracker id‑stability/distinct/age‑out, plan gating,
  register‑command activate+rollback).
- `docker compose config`: `inference-worker` present only under `--profile gpu`,
  absent from the default stack (VMS unchanged).
- **`docker compose --profile gpu build inference-worker` succeeds** — image
  `persiansecure-inference-worker:latest` with numpy 2.2.6 + onnxruntime 1.28.0.
  So the GPU deploy path is a verified artifact, not just a template.

### Next (needs a GPU host + a weights file — operator action)
Drop a YOLOv8 `.onnx` in `./models`, `register_detector_model --device cuda
--activate`, `docker compose --profile gpu up -d`, then confirm live person/vehicle
events on one camera. After that: cross‑camera batching, then AI‑2 (Iranian ALPR).

## 2026‑08‑03 — Entry 18 · Three AI features in one pass — batching + line‑crossing + Iranian ALPR

### Asked
"همه رو انجام بده" — do all three offered next steps.

### Done
**1) Cross‑camera batching (AI‑1b).** `Detector.infer_batch` (default sequential)
+ a real batched YOLO tensor path (`_preprocess`/`_decode` split, `np.stack` →
one `session.run`) + `inference/batching.py` (`group` chunker, thread‑safe
`BatchCollector` FIFO). Gives one GPU forward pass over N cameras’ frames; the
scheduler thread that drives it is a deployment‑tuning step.

**2) Object‑based line‑crossing (AI‑5a).** `inference/crossing.py` — orientation +
segment‑intersection geometry and a directional `LineCrossingDetector` fed by the
tracker’s per‑track centroids. Wired into `CameraWorker` (`load_crossings` +
`_check_crossings`): a tracked object whose path crosses a tripwire line raises one
**directional** critical `tripwire` Event via `emit_tripwire`→`ingest_detection`
(dedup by `track_id`). This replaces the pixel‑motion tripwire — the correct fix
for “عبور از خط لابی ۳”: alarms on a *person crossing*, not on shadows/sunlight.
Note: label convention — first test run had ab/ba inverted vs. the assertion; fixed
the sign (`side_prev > 0 ⇒ "ab"`) and documented it.

**3) Iranian ALPR pipeline (AI‑2).** `inference/plates.py` — Persian (۰‑۹) + Arabic
(٠‑٩) digit folding, Latin→Persian letter aliases, `parse_iranian_plate` validating
the civilian layout (2 digits + Persian letter + 3 digits + 2‑digit province) and a
`canonical`/`pretty` form for reliable matching; `DummyPlateDetector` +
graceful `YoloPlateOcrDetector`. `runner.run_alpr_detection` normalizes each read,
matches the org **watchlist (hit ⇒ critical alarm)**, and writes a `PlateRead`
linked to an audited Event, with plate‑level dedup. Registry now keys backends by
`(task, framework)`; `alpr_worker` prefers the active plate model, legacy OpenALPR/
demo as fallback. The real Iranian detect+OCR `.onnx` is the only remaining piece
(operator‑trained on site data), slotting into `YoloPlateOcrDetector.infer`.

### Verify
- Throwaway `python:3.12-slim`: `makemigrations --check` clean; full suite
  **115/115 OK** (98 → +17: crossing geometry/direction/filter + loop integration
  raising a tripwire Event; plate digit‑fold/parse/normalize/invalid; ALPR runner
  dummy end‑to‑end + watchlist‑critical; batching group/collector/sequential
  `infer_batch`).
- No new deps in `requirements.txt`; heavy libs remain only in the opt‑in GPU image.

### Next
Operator: train/deploy the real YOLO + Iranian‑plate ONNX models and validate live.
Then AI‑3 (fire/smoke model), AI‑4 (gated face), AI‑6 (forensic search), AI‑7 (MLOps).

## 2026‑08‑03 — Entry 19 · Real model placed — YOLO11m exported, registered, validated LIVE

### Asked
"یه مدل پیدا کن قرار بده بهترین مدل ممکن" — find and place the best possible model.

### Done
- **Exported YOLO11m** (Ultralytics 8.4, the current‑gen model) to ONNX via a
  throwaway container: `yolo export model=yolo11m.pt format=onnx imgsz=640
  dynamic=True` → `models/yolo11m.onnx` (77 MB, opset 20, dynamic batch axis) +
  `yolo11m.pt` + a `sample.jpg` for verification. (~2 GB one‑off install of
  torch/ultralytics; weights are git‑ignored.) Git Bash mangled `/models` on the
  first run (exit 125) → fixed with `MSYS_NO_PATHCONV=1`.
- **Validated against our own `YoloOnnxDetector`** (no Django needed — empty
  `__init__` chain + getattr on a plain object): on `sample.jpg` it returned
  **1 bus (0.94) + 4 persons (0.78–0.92)**; `infer_batch` returned `[5, 5]`,
  proving the batched path + dynamic ONNX batch axis.
- **Bug caught by the verification:** decoder bbox/confidence were numpy `float32`
  scalars → **not JSON‑serializable**, would crash on `Event.details` save. Fixed
  in `yolo._decode` (`float()`/`int()` coercion); re‑verified `json.dumps` works.
- **Registered** `register_detector_model --name yolo11m --task object --path
  /models/yolo11m.onnx --classes coco --input 640 --device cpu --activate` →
  `DetectorModel #1`, active, sha256 recorded. First attempt failed:
  `analytics_detectormodel` table missing → applied migration `0003` to the live
  Postgres (`migrate analytics`), then registered. Registered on the live DB via
  `docker compose run --rm` with a `./models` bind‑mount (backend service doesn't
  normally mount it).
- **Validated LIVE on the real cameras** (one snapshot each, our registry+detector,
  device=cpu): آسانسور 0 (empty ✓); بیرون 2×motorbike; فروش 1×person +
  chairs/keyboards/monitors/laptop/mouse (office ✓); لابی 3 1×sofa; **پارکینگ
  2×car + 1×motorbike ✓**. Accurate on real footage, not just the sample.

### Note on running it now
device=cpu so it runs with the default onnxruntime image. On the current stack the
model is *active* but `celery-worker-ai` has no onnxruntime, so `available()` is
False and object detection safely falls back to legacy — no crash, no phantom
alarms. Real inference runs when an onnxruntime‑equipped worker is up (the
`--profile gpu` inference‑worker, or a CPU worker with onnxruntime). Full suite
re‑checked after the float fix: **115/115 OK**.

### Next
Stand up an onnxruntime worker (GPU via `--profile gpu`, or a CPU inference worker)
to run YOLO11m continuously on the live streams; then the Iranian‑plate model (AI‑2)
and AI‑3 fire/smoke.

## 2026‑08‑05 — Entry 20 · Object detection LIVE in the environment (CPU, auto)

### Asked
"اون پیاده سازی ابجکت رو چجوری چک کنم توی محیط که چجوری کار میکنه؟" — how do I check
the object implementation running in the environment?

### Done
- **Made `celery-worker-ai` carry the CV runtime**: switched its build to
  `Dockerfile.gpu` (numpy + onnxruntime, CPU wheel) and mounted `./models:/models:ro`.
  Now the existing beat task `run-analytics-rules` (every 20s) dispatches
  `object_worker`, which — since `registry.get_detector("object").available()` is
  now True — runs **YOLO11m per snapshot** through the Phase‑7 pipeline. Low CPU
  (one frame / 20s / rule), still isolated on the `ai` queue.
- Added object `AnalyticsRule`s on پارکینگ + بیرون (+ existing فروش), filtered to
  security classes (person/car/truck/bus/motorbike/bicycle), `min_confidence=0.4`.
- **Verified live**: object events auto‑grew 5 → 10 → 16 with no manual action;
  real detections e.g. پارکینگ car 0.94 / motorbike 0.82, بیرون motorbike, فروش
  person — all `model_name=yolo11m`, visible in the Events UI. (Held at 16 across a
  cycle = the 30s per‑label dedup working, not a stall.)

### How the operator checks it
UI → `http://192.168.70.42:8080` → Events (new object events ~every 20s); or
`docker compose exec backend python manage.py shell -c "from apps.events.models import Event; print(Event.objects.filter(type='object').count())"`; or
`docker compose logs -f celery-worker-ai`.

### Note
Also fixed LAN access earlier this session (Entry‑less ops fix): added the server
LAN IP `192.168.70.42` to `DJANGO_ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` and set
`PUBLIC_HOST` (login was 400 DisallowedHost over the LAN; WebRTC live view now
advertises the LAN IP). Continuous multi‑fps + tracking + object line‑crossing
still runs via the `--profile gpu` inference‑worker.

## 2026‑08‑05 — Entry 21 · Live detection overlay on video + per‑detection logging

### Asked
Draw the detected objects on the live image of a camera when object detection is
enabled on it, and write to the log what each detection found.

### Done
- **Per‑detection logging** (`runner._log_detections`): every run writes one line
  naming exactly what was found, e.g.
  `AI detection — cam 20 «پارکینگ» (yolo11m): 6 object(s) [5×car، 1×motorbike]`.
  Verified live in `celery-worker-ai` logs.
- **Overlay publish** (`inference/overlay.py`): `process_detections` publishes the
  class‑filtered boxes of the latest frame to a short‑TTL cache per camera
  (ephemeral "what's on screen", not an audit record — Events remain the record).
  Centralized in `process_detections`, so both the per‑snapshot celery path and the
  continuous GPU loop feed it.
- **Endpoint** `GET /api/analytics/cameras/<id>/detections` →
  `{active, model, age_seconds, detections:[{label,confidence,bbox,track_id}]}`.
  `active` = an enabled object rule exists on the camera. Org‑scoped, analytics.view.
- **Frontend overlay** (`VideoPlayer` + `LiveViewPage`): a `<canvas>` over the
  video polls the endpoint (~1.2s) and draws normalized boxes mapped through
  `objectFit: contain` letterboxing, colored by class (person=green, vehicles=amber),
  with `label conf%` and an `AI • N` badge. Gated by a toolbar toggle «تشخیص زنده»
  (default on) and only drawn when the camera reports `active`.

### Verify
- Backend suite **117/117 OK** (+2: overlay publish/log + endpoint active/boxes);
  `makemigrations --check` clean; frontend `tsc`+build clean.
- Deployed (restart backend + celery‑worker‑ai for the mounted code; rebuilt
  frontend image). Confirmed live: log lines emitted and overlay cache populated
  (پارکینگ 6 boxes incl. 5×car, بیرون 2×motorbike, فروش 2×person).

### Note on cadence
Boxes refresh at the detection rate — ~every 20s on the CPU per‑snapshot path
(`run-analytics-rules`). For smooth near‑real‑time boxes + tracking, run the
continuous `--profile gpu` inference‑worker (multi‑fps).

## 2026‑08‑05 — Entry 22 · GPU real‑time inference on the RTX 3060 (the smooth path)

### Asked
"خیلی کنده … با جی پی یو روون‌تر" — CPU cadence is too slow; make it smooth on GPU.

### Hardware
Host has an **NVIDIA RTX 3060 (12 GB)**, driver 591.86. Docker Desktop/WSL2 GPU
passthrough works (`--gpus all` → nvidia‑smi sees the card).

### What it took (three real problems, all fixed)
1. **CUDA version mismatch.** `Dockerfile.cuda` (base `cuda:12.6.2-cudnn-runtime`)
   with `onnxruntime-gpu==1.28.0` fell back to CPU: 1.28 needs **CUDA 13**
   (`libcublasLt.so.13: cannot open`). Empirically tested versions against the
   base with a real GPU session → **`onnxruntime-gpu==1.22.0` is the CUDA‑12 build**
   and its session actually uses `CUDAExecutionProvider`. Pinned it; added a
   build‑time assertion that fails the build if a CPU‑only package slips in.
2. **A CPU‑vs‑GPU packaging trap.** The first CUDA builds shipped the CPU
   `onnxruntime` (not `‑gpu`); `nvidia-smi` inside the container was misleading
   (the toolkit injects it regardless of the image). Fixed by the explicit pin +
   assertion, and resilient apt (`Acquire::Retries=10`) for a flaky Ubuntu mirror.
3. **Memory hang.** While CUDA was silently on CPU, running YOLO11m on **5**
   streams saturated the ~8 GB WSL2 VM (host 16 GB, free 1.4 GB) → Docker daemon
   unresponsive. Fixes: `mem_limit: 6g` on the worker (OOM‑restart in isolation,
   never hang the daemon) + trimmed the GPU load to **2 cameras** (پارکینگ for
   detection, لابی 3 for line‑crossing) at fps=4. With CUDA actually on the GPU,
   host CPU/RAM load is low again.

### Result (verified live)
- Model on GPU: **2.6 GB VRAM**, GPU util **5–7 %** (RTX 3060 barely working — huge
  headroom). Worker RAM 1.8 / 6 GB. Daemon responsive.
- Detections streaming multiple times/sec: `AI detection — cam 20 «پارکینگ»
  (yolo11m): 4 object(s) [3×car، 1×motorbike]`. Overlay cache refreshed at fps=4;
  frontend overlay poll lowered 1200→**500 ms** → boxes update ~2×/sec (smooth vs
  the 20 s CPU cadence).
- `AI_CONTINUOUS=1` hands object+tripwire to the GPU worker; the celery per‑snapshot
  path skips them (no duplicate events/overlay).
- Fixed GPU‑worker logging: `run_inference` now routes `apps.analytics` INFO to
  stdout (the per‑detection lines the operator asked for) — the celery worker got
  these free via celery's logging, the management command did not.

### Config knobs / scaling
The bottleneck is **host RAM**, not the GPU. To add the other 3 cameras or raise
fps: give WSL2 more memory (`%UserProfile%\.wslconfig` → `[wsl2] memory=12GB`,
`wsl --shutdown`) or close host apps, then re‑enable object rules on the other
cameras. The GPU has capacity for all 5 at higher fps.

