# Native development (no Docker)

Run PersianSecure natively while you develop, so Docker's ~6 GB WSL2 VM isn't
competing with VS Code, browsers and your other projects. Docker stays only for
the **final production build/test**.

| Mode | RAM | Use for |
|---|---|---|
| Native dev (this doc) | ~0.6–1 GB | day-to-day coding of the app + UI |
| Docker (`docker compose up`) | ~5–6 GB | production build & full-stack test |

## One-time prerequisites
1. **Python 3.12** — install from python.org (tick "Add python.exe to PATH") or
   `winget install Python.Python.3.12`. Verify: `python --version`.
2. **Node.js** — already installed (`node --version`). Nothing to do.
3. *(optional, only for live video/recording)* **ffmpeg** and **MediaMTX** —
   `winget install Gyan.FFmpeg` and download `mediamtx.exe` from
   github.com/bluenviron/mediamtx/releases. Not needed for app/API/UI work.

## Run it (two terminals)
**Backend** (creates the venv + installs deps on first run):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev-backend.ps1
```
→ http://localhost:8000  (Django, SQLite, in-memory — see `config/settings_dev.py`)

**Frontend**:
```bash
cd frontend
npm run dev
```
→ http://localhost:5173  (Vite proxies `/api`, `/ws`, `/webrtc` to the backend)

First time, create a login:
```powershell
cd backend
.venv\Scripts\python manage.py createsuperuser --settings=config.settings_dev
```

## What works natively vs. needs binaries
- ✅ **Works out of the box:** login, dashboard, cameras/config, events, analytics
  UI, users/roles, playback UI, the REST API — everything that is app logic.
- ⚙️ **Eager Celery:** background tasks run inline; periodic jobs (recording index,
  health, retention) don't self-schedule in dev. Trigger them manually if needed,
  e.g. `... manage.py shell -c "from apps.recordings.tasks import index_recordings; index_recordings()"`.
- 📹 **Live video + recording:** need MediaMTX + ffmpeg running (optional). Start
  `mediamtx.exe` with `media_server/mediamtx.yml`; the Vite proxy already points
  `/webrtc`→8889, `/hls`→8888.

The dev **SQLite** DB (`backend/db.sqlite3`) is completely separate from the Docker
Postgres — your production data is never touched.

## Keep Docker from eating RAM in the background
Docker Desktop currently **starts on login** and immediately consumes the WSL2 VM.
Turn it off: **Docker Desktop → Settings → General → uncheck "Start Docker Desktop
when you sign in"**. Start Docker only when you need the full stack.

A safety cap is already set in `%USERPROFILE%\.wslconfig` (`memory=6GB`) so that,
even when Docker does run, it can never exhaust host RAM and freeze Windows.

## Going to production
When you're ready to ship, the Docker path is unchanged:
```bash
docker compose up -d --build      # full stack (Postgres/Redis/MediaMTX/…)
```
The GPU inference worker (`--profile gpu`) needs more RAM than is safe on this
16 GB dev box — run it on the production host, or after freeing host RAM.
