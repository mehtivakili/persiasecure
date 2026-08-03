# پرشین‌سکیور | PersianSecure

سامانه نظارت تصویری ابری (VSaaS) به سبک Genetec Security Center و Milestone XProtect،
به زبان فارسی (RTL) با Django + React. این نسخه، «هستهٔ VMS» است: مدیریت دوربین،
نمای زنده، ضبط و بازپخش، رویدادها/هشدارها، کاربران و نقش‌ها (RBAC) و داشبورد فارسی.

> A Persian, RTL Video-Surveillance-as-a-Service platform (Genetec/Milestone-style),
> built with Django + React. This release is the **Core VMS foundation**.
> Data model and ffmpeg/ONVIF concepts are inspired by the open-source **Shinobi** NVR.

> **Readiness notice:** advanced analytics and phase-2 modules are disabled by
> default. See [the supported baseline](docs/supported-baseline.md) before using
> this project outside development. Demo data and synthetic detections now
> require explicit opt-in flags.

---

## ویژگی‌ها | Features
- 🎥 **مدیریت دوربین**: RTSP و کشف/دریافت اطلاعات از طریق ONVIF، آزمایش اتصال، PTZ.
- 🟩 **نمای زنده**: شبکهٔ ۱/۴/۹/۱۶ با پخش کم‌تأخیر WebRTC (WHEP) و fallback به HLS.
- ⏺ **ضبط و بازپخش**: حالت‌های پیوسته/حرکتی/زمان‌بندی‌شده، نگهداری خودکار، خروجی گرفتن (Export).
- 🚨 **رویدادها و هشدارها**: فید زندهٔ WebSocket، تأیید/رفع، شدت‌بندی.
- 👥 **کاربران و نقش‌ها**: کنترل دسترسی مبتنی بر نقش + گزارش ممیزی (Audit).
- 📊 **داشبورد فارسی**: شاخص‌ها، وضعیت دوربین‌ها، نمودار رویدادها.
- 🌐 چندسازمانی (Multi-tenant)، رابط کاملاً راست‌به‌چپ با فونت وزیرمتن.

### ماژول‌های پیشرفته (فاز ۲) | Advanced modules (phase 2)
- 🔍 **تحلیل تصویر**: پلاک‌خوان (ALPR)، تشخیص شیء و حرکت با موتور تشخیص افزونه‌ای، فهرست پلاک‌های تحت نظر.
- 🚪 **کنترل تردد**: درها (باز/قفل)، دارندگان کارت و اعتبارنامه‌ها، رویدادهای تردد.
- 🗺️ **نقشه‌ها**: بارگذاری پلان و قراردادن نشانگر دوربین/در روی نقشه.
- 🌐 **فدراسیون چندسروری**: اتصال و همگام‌سازی دوربین‌های سایت‌های دیگر.
- ⚖️ **مدیریت مدارک**: پرونده‌ها، زنجیرهٔ حفاظت (custody) و بررسی صحت با SHA256.
> موتورهای تشخیص فعلاً به‌صورت افزونه‌ای (stub) پاسخ نمونه می‌دهند؛ آمادهٔ اتصال به OpenALPR/OpenCV/YOLO.

## معماری | Architecture
```
React (Vite+TS, MUI RTL, i18n)  ──REST + WebSocket──▶  Django (DRF + Channels)
        │  WebRTC/HLS                                        │  Celery + Redis
        ▼                                                    ▼
     MediaMTX ◀── RTSP/ONVIF ── دوربین‌ها          health-check / index / motion / retention
        └── قطعات ضبط (mp4/fmp4) روی والیوم مشترک ──▶ ایندکس در Postgres
```

اجزای Docker Compose: `postgres`, `redis`, `mediamtx`, `backend` (ASGI/uvicorn),
`celery-worker`, `celery-beat`, `frontend` (nginx).

## اجرا با Docker | Run with Docker
```bash
cp .env.example .env      # مقادیر را تنظیم کنید (رمزها، کلید مخفی)
docker compose up --build
```
- رابط کاربری: http://localhost:8080
- پنل مدیریت Django: http://localhost:8080/admin
- سرور رسانه (WebRTC): http://localhost:8889 — (HLS: 8888، RTSP: 8554)

هیچ حساب یا دادهٔ نمونه‌ای به‌صورت پیش‌فرض ساخته نمی‌شود. مدیر نخست را به‌شکل
تعاملی ایجاد کنید:
```bash
docker compose exec backend python manage.py bootstrap_admin
```

برای اجرای صریح محیط نمایشی، `SEED_DEMO_DATA=1`،
`ENABLE_DEMO_ANALYTICS=1` و `FEATURE_ANALYTICS=1` را تنظیم کنید و سپس اجرا کنید:
```bash
docker compose --profile demo up --build
```

## توسعهٔ محلی | Local development
بک‌اند بدون Docker (SQLite + channel layer درون‌حافظه‌ای):
```bash
cd backend
../scripts/bootstrap-dev.ps1                    # ویندوز
.venv/Scripts/activate
python manage.py migrate
python manage.py bootstrap_admin
python manage.py runserver 127.0.0.1:8000
```
> اگر متغیر `POSTGRES_HOST` تنظیم نشده باشد، به‌صورت خودکار از SQLite استفاده می‌شود.

فرانت‌اند:
```bash
cd frontend
npm install
npm run dev     # http://localhost:5173  (پروکسی /api و /ws به بک‌اند)
```

## ساختار پروژه | Layout
```
persiansecure/
├── docker-compose.yml   .env.example
├── media_server/mediamtx.yml
├── backend/  (Django: config + apps/{accounts,cameras,recordings,events,dashboard,analytics,mediactl})
└── frontend/ (React: features/{auth,dashboard,liveview,playback,cameras,events,users})
```

## نقشهٔ راه (فاز بعد) | Roadmap
تحلیل تصویر (پلاک‌خوان ALPR، تشخیص شیء/چهره)، کنترل تردد (Access Control)، نقشه‌ها،
فدراسیون چندسروری، زنجیرهٔ حفاظت مدارک (Evidence)، و اپ موبایل — هم‌اکنون به‌صورت
اسکلت (stub) در اپ `analytics` و مدل‌ها آماده شده‌اند.

## اعتبار | Credits
مدل داده و مفاهیم ffmpeg/ONVIF با الهام از پروژهٔ متن‌باز
[Shinobi](https://gitlab.com/Shinobi-Systems/Shinobi). پخش زنده مبتنی بر
[MediaMTX](https://github.com/bluenviron/mediamtx).
