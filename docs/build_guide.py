# -*- coding: utf-8 -*-
"""
Builds the PersianSecure user guide as a self-contained HTML file (Vazirmatn
font embedded as base64) which is then converted to PDF with headless Chrome.
No third-party Python packages required.
"""
import base64
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def font_b64(name):
    return base64.b64encode((HERE / "fonts" / name).read_bytes()).decode("ascii")


REG = font_b64("Vazirmatn-Regular.ttf")
BOLD = font_b64("Vazirmatn-Bold.ttf")

# ---------------------------------------------------------------------------
HTML = r"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<style>
@font-face{font-family:'Vazirmatn';font-weight:400;src:url(data:font/ttf;base64,__REG__) format('truetype');}
@font-face{font-family:'Vazirmatn';font-weight:700;src:url(data:font/ttf;base64,__BOLD__) format('truetype');}
@page{size:A4;margin:18mm 16mm;}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;font-family:'Vazirmatn',Tahoma,sans-serif;color:#1a2431;font-size:11.5pt;line-height:1.85;}
h1,h2,h3{color:#0f3f6b;line-height:1.4;}
h2{font-size:17pt;border-bottom:2px solid #3da5ff;padding-bottom:5px;margin-top:26px;}
h3{font-size:13.5pt;color:#155a9c;margin-top:18px;}
p{margin:8px 0;text-align:justify;}
ul,ol{margin:8px 0;padding-inline-start:22px;}
li{margin:4px 0;}
code,.code{font-family:'Consolas','Courier New',monospace;direction:ltr;unicode-bidi:embed;text-align:left;}
code{background:#eef4fb;color:#0f3f6b;padding:1px 6px;border-radius:5px;font-size:10pt;}
.code{display:block;background:#0f1a26;color:#d6e6f5;padding:12px 14px;border-radius:9px;margin:10px 0;font-size:9.5pt;white-space:pre-wrap;overflow-wrap:anywhere;}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:10.2pt;}
th,td{border:1px solid #cdd9e6;padding:7px 9px;text-align:right;vertical-align:top;}
th{background:#eaf3fc;color:#0f3f6b;font-weight:700;}
td[dir=ltr],th[dir=ltr]{text-align:left;font-family:'Consolas',monospace;}
.note{background:#eef7ff;border-inline-start:4px solid #3da5ff;padding:9px 13px;border-radius:8px;margin:12px 0;}
.warn{background:#fff5ec;border-inline-start:4px solid #ff8c1a;padding:9px 13px;border-radius:8px;margin:12px 0;}
.danger{background:#fdeeee;border-inline-start:4px solid #ff5a5f;padding:9px 13px;border-radius:8px;margin:12px 0;}
.tag{display:inline-block;background:#e8f0f8;color:#155a9c;border:1px solid #c4d8ec;border-radius:6px;padding:1px 9px;font-size:9.5pt;margin:2px;}
.step{background:#f7fafd;border:1px solid #dbe7f2;border-radius:9px;padding:10px 14px;margin:10px 0;}
.path{background:#0f3f6b;color:#fff;border-radius:6px;padding:2px 9px;font-weight:700;font-size:10pt;white-space:nowrap;}

/* Cover */
.cover{height:257mm;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;page-break-after:always;
  background:radial-gradient(900px 500px at 70% 10%,#e7f2ff,transparent),linear-gradient(160deg,#0f1a26,#123a63);color:#fff;border-radius:14px;}
.cover .shield{width:96px;height:96px;border-radius:22px;background:linear-gradient(135deg,#3da5ff,#1f7fe0);display:flex;align-items:center;justify-content:center;font-size:54px;box-shadow:0 20px 50px -18px rgba(61,165,255,.9);margin-bottom:22px;}
.cover h1{color:#fff;font-size:40pt;margin:6px 0;}
.cover .sub{color:#bcd6f0;font-size:15pt;}
.cover .meta{margin-top:34px;color:#9fc0e0;font-size:11pt;}
.toc a{color:#155a9c;text-decoration:none;}
.toc li{margin:6px 0;}
.pagebreak{page-break-before:always;}
.arch{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0;}
.arch .b{flex:1;min-width:150px;background:#f2f8fd;border:1px solid #cfe0f0;border-radius:9px;padding:9px 12px;font-size:10pt;}
.arch .b b{color:#0f3f6b;}
small{color:#5c6b7d;}
</style>
</head>
<body>

<!-- ============ COVER ============ -->
<div class="cover">
  <div class="shield">🛡️</div>
  <h1>پرشین‌سکیور</h1>
  <div class="sub">سامانه نظارت تصویری ابری (VSaaS)</div>
  <div class="sub" style="font-size:12pt;margin-top:8px;">راهنمای جامع کاربری و راه‌اندازی</div>
  <div class="meta">نسخه ۰٫۲ &nbsp;|&nbsp; مبتنی بر Django + React + MediaMTX<br>سکوی مدیریت دوربین، کنترل تردد و تحلیل هوشمند تصویر</div>
</div>

<!-- ============ TOC ============ -->
<h2>فهرست مطالب</h2>
<ol class="toc">
  <li>معرفی سامانه</li>
  <li>معماری فنی</li>
  <li>راه‌اندازی و ورود</li>
  <li>بخش‌های سامانه</li>
  <li><b>اتصال دوربین واقعی (RTSP و ONVIF)</b></li>
  <li>اعلان‌های پیامکی و تماس</li>
  <li>تحلیل‌های ایمنی: خط مجازی، آتش، دود، نقشه حرارتی</li>
  <li>عیب‌یابی</li>
  <li>پیوست‌ها: پورت‌ها و مقادیر پیش‌فرض</li>
</ol>

<!-- ============ 1 ============ -->
<h2>۱. معرفی سامانه</h2>
<p><b>پرشین‌سکیور</b> یک سکوی کامل «نظارت تصویری به‌عنوان سرویس» (VSaaS) به زبان فارسی و راست‌به‌چپ است که برای مدیریت متمرکز دوربین‌های مداربسته، کنترل تردد و تحلیل هوشمند تصویر طراحی شده و از نظر قابلیت‌ها هم‌تراز با سامانه‌هایی مانند Genetec Security Center و Milestone XProtect است.</p>
<p>این سامانه به‌صورت کاملاً وب‌محور اجرا می‌شود؛ اپراتور تنها با یک مرورگر به آدرس سرور متصل می‌شود و به تمام امکانات دسترسی دارد. ویدیوی زنده با تأخیر پایین (WebRTC) و پخش جایگزین (HLS) ارائه می‌شود.</p>
<p><b>قابلیت‌های اصلی:</b></p>
<div>
<span class="tag">نمای زنده چنددوربینه</span><span class="tag">ضبط و بازپخش</span><span class="tag">پلاک‌خوان (ALPR)</span>
<span class="tag">تشخیص شیء</span><span class="tag">تشخیص آتش و دود</span><span class="tag">خط مجازی</span><span class="tag">نقشه حرارتی</span>
<span class="tag">کنترل تردد و درها</span><span class="tag">نقشه و پلان</span><span class="tag">خودکارسازی رویداد→عملیات</span>
<span class="tag">هشدار پیامک و تماس</span><span class="tag">فدراسیون چندسروری</span><span class="tag">مدیریت مدارک</span>
<span class="tag">گزارش‌گیری</span><span class="tag">پایش سلامت</span><span class="tag">سطح تهدید</span><span class="tag">کنترل دسترسی مبتنی بر نقش</span>
</div>

<!-- ============ 2 ============ -->
<h2>۲. معماری فنی</h2>
<p>سامانه از چند سرویس مستقل تشکیل شده که در کنار هم (با Docker Compose) اجرا می‌شوند:</p>
<div class="arch">
  <div class="b"><b>Frontend</b><br>React + TypeScript، رابط راست‌به‌چپ با فونت وزیرمتن. پخش WebRTC/HLS.</div>
  <div class="b"><b>Backend</b><br>Django + DRF + Channels. مغز سامانه، API و وب‌سوکت رویدادها.</div>
  <div class="b"><b>MediaMTX</b><br>سرور رسانه: دریافت RTSP/ONVIF و بازپخش به‌صورت WebRTC/HLS و ضبط.</div>
  <div class="b"><b>Celery + Redis</b><br>پردازش پس‌زمینه: سلامت دوربین، ضبط، تحلیل تصویر، ارسال پیامک.</div>
  <div class="b"><b>PostgreSQL</b><br>پایگاه داده اصلی: دوربین‌ها، رویدادها، کاربران، تنظیمات.</div>
  <div class="b"><b>test-video</b><br>سرویس دوربین مصنوعی برای آزمایش بدون سخت‌افزار.</div>
</div>
<p><b>مسیر جریان تصویر:</b> دوربین (RTSP) ← MediaMTX (بازپخش و ضبط) ← مرورگر (WebRTC). هم‌زمان، کارگرهای Celery فریم‌ها را برای تشخیص حرکت/آتش/دود/پلاک نمونه‌برداری می‌کنند و رویدادها را از طریق وب‌سوکت به‌صورت زنده به رابط کاربری می‌فرستند.</p>

<!-- ============ 3 ============ -->
<h2 class="pagebreak">۳. راه‌اندازی و ورود</h2>
<h3>اجرا با Docker</h3>
<p>در پوشهٔ پروژه، فایل <code>.env.example</code> را به <code>.env</code> کپی کرده و مقادیر را تنظیم کنید، سپس:</p>
<div class="code">cd persiansecure
cp .env.example .env
docker compose up --build</div>
<p>پس از بالا آمدن سرویس‌ها، رابط کاربری از این آدرس در دسترس است:</p>
<div class="step">🌐 آدرس: <code>http://localhost:8080</code></div>
<div class="note">هیچ حساب یا دادهٔ نمایشی به‌صورت پیش‌فرض ساخته نمی‌شود. مدیر نخست را با فرمان <code>docker compose exec backend python manage.py bootstrap_admin</code> ایجاد کنید.</div>

<!-- ============ 4 ============ -->
<h2>۴. بخش‌های سامانه</h2>
<table>
<tr><th style="width:26%">بخش</th><th>کاربرد</th></tr>
<tr><td>داشبورد</td><td>نمای کلی: تعداد دوربین‌ها، آنلاین/آفلاین، رویدادهای ۲۴ ساعت، هشدارهای تأییدنشده، نمودار روند و آخرین هشدارها.</td></tr>
<tr><td>نمای زنده</td><td>مشاهدهٔ هم‌زمان دوربین‌ها در چیدمان ۱/۴/۹/۱۶؛ «تور دوربین» (چرخش خودکار)، «دیوار تصویری» (تمام‌صفحه)، عکس فوری و کنترل PTZ.</td></tr>
<tr><td>بازپخش</td><td>انتخاب دوربین و تاریخ (تقویم شمسی)، مرور قطعات ضبط‌شده، پخش، نشانک‌گذاری و خروجی گرفتن از بازهٔ زمانی.</td></tr>
<tr><td>دوربین‌ها</td><td>افزودن/ویرایش دوربین، کشف ONVIF، آزمایش اتصال، تعیین حالت ضبط و نگهداری.</td></tr>
<tr><td>رویدادها</td><td>فهرست زندهٔ هشدارها با تصویر لحظهٔ وقوع؛ تأیید و رفع هشدار.</td></tr>
<tr><td>تحلیل تصویر</td><td>قوانین پلاک‌خوان، تشخیص شیء، حرکت، آتش، دود و خط مجازی؛ نقشهٔ حرارتی و فهرست پلاک‌های تحت نظر.</td></tr>
<tr><td>کنترل تردد</td><td>درها (باز/قفل)، دارندگان کارت، اعتبارنامه‌ها و رویدادهای تردد.</td></tr>
<tr><td>نقشه‌ها</td><td>بارگذاری پلان ساختمان و قراردادن نشانگر دوربین/در روی آن.</td></tr>
<tr><td>خودکارسازی</td><td>قوانین «رویداد ← عملیات»: هر رویداد می‌تواند پیامک، تماس، باز/قفل در، وب‌هوک یا تغییر سطح تهدید را فعال کند.</td></tr>
<tr><td>فدراسیون</td><td>اتصال و همگام‌سازی دوربین‌های سرورهای دیگر (سایت‌های متعدد).</td></tr>
<tr><td>مدارک</td><td>پرونده‌سازی، زنجیرهٔ حفاظت و بررسی صحت با کد SHA256.</td></tr>
<tr><td>گزارش‌ها</td><td>خروجی CSV از رویدادها، ترددها و پلاک‌ها با بازهٔ تاریخ شمسی.</td></tr>
<tr><td>سلامت سامانه</td><td>وضعیت سرویس‌ها (پایگاه‌داده، Redis، سرور رسانه، پردازش پس‌زمینه)، فضای ذخیره‌سازی و وضعیت دوربین‌ها.</td></tr>
<tr><td>کاربران و نقش‌ها</td><td>مدیریت کاربران و کنترل دسترسی مبتنی بر نقش (RBAC).</td></tr>
<tr><td>تنظیمات</td><td>مدیریت شماره‌های دریافت‌کنندهٔ هشدار و پیکربندی سرویس پیامک/تماس.</td></tr>
</table>

<!-- ============ 5 — CAMERA ============ -->
<h2 class="pagebreak">۵. اتصال دوربین واقعی</h2>
<p>سامانه از هر دوربین تحت‌شبکه (IP Camera) که از پروتکل استاندارد <b>RTSP</b> یا <b>ONVIF</b> پشتیبانی کند، پشتیبانی می‌کند — یعنی تقریباً تمام دوربین‌های صنعتی امروزی (Hikvision، Dahua، Axis، Reolink، Hanwha و…). دو روش برای افزودن دوربین وجود دارد.</p>

<h3>۵٫۱ روش اول: آدرس RTSP مستقیم (ساده‌ترین)</h3>
<div class="step">
۱) از منو وارد <span class="path">دوربین‌ها</span> شوید و روی <b>«افزودن دوربین»</b> کلیک کنید.<br>
۲) نام و محل نصب را وارد کنید.<br>
۳) در فیلد <b>«آدرس کامل RTSP»</b>، نشانی استریم دوربین را وارد کنید (قالب هر برند در جدول زیر).<br>
۴) نام کاربری و گذرواژهٔ دوربین را در فیلدهای مربوطه وارد کنید.<br>
۵) روی <b>«آزمایش اتصال»</b> بزنید؛ اگر پیام «اتصال برقرار است» دیدید، روی <b>«ذخیره»</b> کلیک کنید.<br>
۶) دوربین بلافاصله در «نمای زنده» و داشبورد ظاهر می‌شود.
</div>
<p><b>قالب آدرس RTSP برندهای رایج</b> (به‌جای <code>user</code>، <code>pass</code> و <code>IP</code> مقادیر دوربین خود را بگذارید):</p>
<table>
<tr><th style="width:22%">برند</th><th>نمونه آدرس RTSP</th></tr>
<tr><td>Hikvision</td><td dir="ltr">rtsp://user:pass@IP:554/Streaming/Channels/101</td></tr>
<tr><td>Dahua</td><td dir="ltr">rtsp://user:pass@IP:554/cam/realmonitor?channel=1&subtype=0</td></tr>
<tr><td>Axis</td><td dir="ltr">rtsp://user:pass@IP:554/axis-media/media.amp</td></tr>
<tr><td>Reolink</td><td dir="ltr">rtsp://user:pass@IP:554/h264Preview_01_main</td></tr>
<tr><td>Hanwha / سامسونگ</td><td dir="ltr">rtsp://user:pass@IP:554/profile2/media.smp</td></tr>
<tr><td>عمومی (ONVIF)</td><td dir="ltr">rtsp://user:pass@IP:554/onvif1</td></tr>
</table>
<div class="note">در قالب Hikvision، عدد <code>101</code> یعنی «کانال ۱، استریم اصلی» و <code>102</code> یعنی «استریم فرعی (Sub)». برای شبکه‌های پرترافیک، استریم فرعی برای تحلیل و استریم اصلی برای ضبط توصیه می‌شود.</div>

<h3>۵٫۲ روش دوم: کشف خودکار با ONVIF</h3>
<p>اگر آدرس RTSP دوربین را نمی‌دانید، از ONVIF استفاده کنید تا سامانه آن را خودکار پیدا کند:</p>
<div class="step">
۱) در فرم افزودن دوربین، بخش <b>ONVIF</b> را پر کنید: <b>ONVIF host</b> (همان IP دوربین)، <b>پورت</b> (معمولاً ۸۰ یا ۸۰۰۰)، نام کاربری و گذرواژه.<br>
۲) روی <b>«دریافت اطلاعات دستگاه»</b> بزنید؛ سامانه سازنده/مدل و آدرس RTSP را به‌صورت خودکار پر می‌کند.<br>
۳) با «آزمایش اتصال» بررسی و سپس «ذخیره» کنید.
</div>

<h3>۵٫۳ نکات شبکه و پورت</h3>
<ul>
<li>دوربین و سرور پرشین‌سکیور باید در یک شبکه باشند یا مسیر شبکه‌ای بین آن‌ها برقرار باشد.</li>
<li>پورت پیش‌فرض RTSP معمولاً <code>554</code> و پورت ONVIF <code>80</code> یا <code>8000</code> است.</li>
<li>اگر سرور داخل Docker اجرا می‌شود، مطمئن شوید کانتینر به شبکهٔ دوربین‌ها دسترسی دارد (شبکهٔ host یا bridge با مسیریابی مناسب).</li>
<li>برای دسترسی از بیرون شبکه، به‌جای باز کردن پورت دوربین، دسترسی را از طریق همین سامانه بدهید (امن‌تر است).</li>
</ul>

<h3>۵٫۴ ضبط و کیفیت</h3>
<p>پس از افزودن دوربین، در فرم ویرایش، بخش <b>«ضبط»</b> حالت ضبط را تعیین می‌کند:</p>
<table>
<tr><th style="width:26%">حالت</th><th>توضیح</th></tr>
<tr><td>خاموش</td><td>بدون ضبط؛ فقط نمای زنده.</td></tr>
<tr><td>پیوسته</td><td>ضبط دائمی به‌صورت قطعات (پیش‌فرض دوربین نمونه).</td></tr>
<tr><td>مبتنی بر حرکت</td><td>ضبط هنگام تشخیص حرکت.</td></tr>
<tr><td>زمان‌بندی‌شده</td><td>ضبط در بازه‌های تعریف‌شدهٔ هفتگی.</td></tr>
</table>
<p>مدت <b>نگهداری (روز)</b> تعیین می‌کند ضبط‌های قدیمی پس از چند روز به‌صورت خودکار حذف شوند.</p>

<h3>۵٫۵ عیب‌یابی اتصال دوربین</h3>
<table>
<tr><th style="width:34%">نشانه</th><th>راه‌حل</th></tr>
<tr><td>«اتصال ناموفق» در آزمایش</td><td>آدرس RTSP، نام کاربری/گذرواژه و دسترسی شبکه‌ای را بررسی کنید. آدرس را در VLC هم امتحان کنید.</td></tr>
<tr><td>تصویر سیاه/بدون سیگنال در نمای زنده</td><td>استریم on-demand است؛ چند ثانیه صبر کنید. اگر کدک دوربین H.265 است، در صورت امکان روی H.264 تنظیم کنید.</td></tr>
<tr><td>قطع‌وصل مکرر</td><td>در پروفایل استریم، ترابرد را روی <code>tcp</code> بگذارید (به‌جای udp).</td></tr>
<tr><td>دوربین «آفلاین» در داشبورد</td><td>وظیفهٔ سلامت هر ۳۰ ثانیه بررسی می‌کند؛ در «سلامت سامانه» وضعیت سرور رسانه را ببینید.</td></tr>
</table>

<!-- ============ 6 — SMS ============ -->
<h2 class="pagebreak">۶. اعلان‌های پیامکی و تماس</h2>
<p>هنگام وقوع رویدادهای بحرانی (آتش، دود، عبور از خط و…) سامانه می‌تواند به شماره‌های تعیین‌شده پیامک بفرستد یا تماس بگیرد. این تنظیمات در بخش <span class="path">تنظیمات</span> انجام می‌شود.</p>

<h3>۶٫۱ افزودن شماره‌های دریافت‌کننده</h3>
<div class="step">
۱) وارد <span class="path">تنظیمات</span> شوید.<br>
۲) در پنل «شماره‌های دریافت‌کننده هشدار» روی <b>«افزودن شماره»</b> بزنید.<br>
۳) نام و شمارهٔ تلفن را وارد کنید (مثال: <code>+989121234567</code>).<br>
۴) کلیدهای <b>پیامک</b> و <b>تماس</b> را برای هر شماره روشن/خاموش کنید.<br>
۵) با دکمهٔ <b>«پیامک آزمایشی»</b> صحت تنظیمات را بررسی و سپس <b>«ذخیره»</b> کنید.
</div>

<h3>۶٫۲ انتخاب سرویس ارسال</h3>
<table>
<tr><th style="width:24%">سرویس</th><th>توضیح</th></tr>
<tr><td>حالت آزمایشی (console)</td><td>پیش‌فرض؛ پیام‌ها به‌جای ارسال واقعی در لاگ ثبت می‌شوند. برای آزمایش کل زنجیره بدون حساب.</td></tr>
<tr><td>کاوه‌نگار (ایران)</td><td>ارسال واقعی پیامک و تماس صوتی در ایران. به «کلید API» و «شماره خط ارسال» نیاز دارد.</td></tr>
<tr><td>Twilio (بین‌المللی)</td><td>ارسال بین‌المللی. به Account SID، Auth Token و شمارهٔ مبدأ نیاز دارد.</td></tr>
</table>
<div class="note">برای فعال‌سازی ارسال واقعی، در پنل تنظیمات سرویس «کاوه‌نگار» را انتخاب و کلید API خود را وارد کنید؛ یا همان مقادیر را در فایل <code>.env</code> قرار دهید (<code>SMS_PROVIDER=kavenegar</code> و <code>KAVENEGAR_API_KEY=...</code>). مقادیر پنل بر مقادیر <code>.env</code> اولویت دارند.</div>

<h3>۶٫۳ نحوهٔ کار هشدار خودکار</h3>
<p>سه قانون خودکارسازی از پیش ساخته شده‌اند: <span class="tag">آتش → پیامک</span> <span class="tag">دود → پیامک</span> <span class="tag">عبور از خط → پیامک</span>. این قوانین به‌صورت خودکار به تمام شماره‌های ثبت‌شده در تنظیمات پیامک می‌فرستند. برای تغییر یا افزودن عملیات (مثلاً تماس صوتی یا باز کردن در)، به بخش <span class="path">خودکارسازی</span> بروید.</p>

<!-- ============ 7 — SAFETY ============ -->
<h2 class="pagebreak">۷. تحلیل‌های ایمنی</h2>

<h3>۷٫۱ خط مجازی (Tripwire)</h3>
<p>با این قابلیت می‌توانید روی تصویر دوربین یک خط فرضی بکشید؛ هر شخص یا شیئی که از آن عبور کند، هشدار بحرانی همراه با تصویر و پیامک ایجاد می‌شود.</p>
<div class="step">
۱) وارد <span class="path">تحلیل تصویر</span> شوید، تب «قوانین»، روی «افزودن قانون».<br>
۲) دوربین را انتخاب و نوع را روی <b>«عبور از خط»</b> بگذارید.<br>
۳) روی تصویر زندهٔ دوربین <b>دو بار کلیک کنید</b> تا دو سر خط مشخص شود.<br>
۴) ذخیره کنید. از این پس عبور از این خط، هشدار بحرانی و پیامک ایجاد می‌کند.
</div>

<h3>۷٫۲ تشخیص آتش و دود</h3>
<p>قوانین «تشخیص آتش» و «تشخیص دود» فریم‌ها را برای نشانه‌های رنگی آتش (نارنجی/قرمز داغ) و هالهٔ دود بررسی می‌کنند. هنگام تشخیص، هشدار بحرانی همراه با تصویر و پیامک صادر می‌شود.</p>
<div class="warn">تا زمان نصب مدل هوش مصنوعی اختصاصی، این دو قابلیت در «حالت نمایشی (demo)» اجرا می‌شوند تا کل زنجیرهٔ هشدار (رویداد ← پیامک) قابل آزمایش باشد. برای دقت عملیاتی، مدل واقعی (مانند YOLO یا OpenALPR برای پلاک) قابل جایگزینی است.</div>

<h3>۷٫۳ نقشهٔ حرارتی حرکت</h3>
<p>در تب «نقشه حرارتی»، دوربین و بازهٔ زمانی (۱/۷/۳۰ روز) را انتخاب کنید تا نقاط پرتردد به‌صورت نواحی قرمزرنگ روی تصویر دوربین نمایش داده شوند — برای تحلیل الگوی رفت‌وآمد.</p>

<h3>۷٫۴ پلاک‌خوان و فهرست تحت نظر</h3>
<p>در تب «فهرست تحت نظر» می‌توانید پلاک‌های موردنظر را ثبت کنید؛ اگر پلاک‌خوان چنین پلاکی را ببیند، هشدار <b>بحرانی</b> صادر می‌شود.</p>

<!-- ============ 8 — TROUBLESHOOT ============ -->
<h2 class="pagebreak">۸. عیب‌یابی عمومی</h2>
<ul>
<li>وضعیت کلی سرویس‌ها را در بخش <span class="path">سلامت سامانه</span> ببینید (پایگاه‌داده، Redis، سرور رسانه، پردازش پس‌زمینه باید «سالم» باشند).</li>
<li>اگر رابط کاربری بالا نمی‌آید، اجرای کانتینرها را بررسی کنید: <code>docker compose ps</code></li>
<li>برای دیدن لاگ یک سرویس: <code>docker compose logs backend</code> یا <code>docker compose logs celery-worker</code></li>
<li>پیام‌های پیامک در حالت آزمایشی در لاگ <code>celery-worker</code> با نشانهٔ <code>[SMS→...]</code> دیده می‌شوند.</li>
</ul>

<!-- ============ APPENDIX ============ -->
<h2>۹. پیوست‌ها</h2>
<h3>پیوست الف — جدول پورت‌ها</h3>
<table>
<tr><th style="width:26%">سرویس</th><th dir="ltr">پورت</th><th>کاربرد</th></tr>
<tr><td>رابط کاربری (nginx)</td><td dir="ltr">8080</td><td>دسترسی وب به سامانه</td></tr>
<tr><td>MediaMTX — WebRTC</td><td dir="ltr">8889</td><td>پخش زندهٔ کم‌تأخیر</td></tr>
<tr><td>MediaMTX — HLS</td><td dir="ltr">8888</td><td>پخش جایگزین</td></tr>
<tr><td>MediaMTX — RTSP</td><td dir="ltr">8554</td><td>بازپخش/دریافت داخلی</td></tr>
<tr><td>دوربین — RTSP</td><td dir="ltr">554</td><td>استریم دوربین</td></tr>
<tr><td>دوربین — ONVIF</td><td dir="ltr">80/8000</td><td>کشف و کنترل دوربین</td></tr>
</table>

<h3>پیوست ب — مقادیر پیش‌فرض</h3>
<table>
<tr><th style="width:34%">مورد</th><th>مقدار پیش‌فرض</th></tr>
<tr><td>آدرس رابط کاربری</td><td dir="ltr">http://localhost:8080</td></tr>
<tr><td>نام کاربری مدیر</td><td>هنگام اجرای bootstrap_admin تعیین می‌شود</td></tr>
<tr><td>گذرواژهٔ مدیر</td><td>مقدار پیش‌فرض ندارد</td></tr>
<tr><td>پنل مدیریت Django</td><td dir="ltr">http://localhost:8080/admin</td></tr>
<tr><td>شمارهٔ هشدار پیش‌فرض</td><td dir="ltr">ALARM_PHONE در .env</td></tr>
</table>
<div class="danger">توصیهٔ امنیتی: یک گذرواژهٔ قوی برای مدیر تعیین کنید و کلید <code>DJANGO_SECRET_KEY</code> را در <code>.env</code> به یک مقدار تصادفی و طولانی تنظیم کنید. قابلیت‌ها و داده‌های نمایشی را در محیط عملیاتی فعال نکنید.</div>

<p style="text-align:center;margin-top:40px;color:#5c6b7d;">— پایان راهنما —<br><b style="color:#0f3f6b;">پرشین‌سکیور</b> · سامانه نظارت تصویری ابری فارسی</p>

</body>
</html>
"""

out_html = HERE / "PersianSecure-Guide.html"
out_html.write_text(HTML.replace("__REG__", REG).replace("__BOLD__", BOLD), encoding="utf-8")
print(f"wrote {out_html} ({out_html.stat().st_size} bytes)")
