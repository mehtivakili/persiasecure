"""
Camera brand presets — RTSP URL templates for common CCTV manufacturers.

The app works with ANY camera that speaks RTSP or ONVIF; these presets just
save the installer from looking up each vendor's stream path. `{ch}` is the
1-based channel number (relevant for NVRs / multi-channel encoders).

IMPORTANT: vendors change paths between firmware versions and OEM rebrands are
common. The authoritative way to obtain a camera's exact stream URI is the
ONVIF probe (`POST /api/cameras/onvif/probe`), which asks the device itself.
These templates are best-effort starting points — always confirm with
"آزمایش اتصال" (Test connection) after saving.
"""

CAMERA_BRANDS = [
    {
        "id": "onvif",
        "label": "کشف خودکار (ONVIF) — توصیه‌شده",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "",
        "sub": "",
        "note": "دقیق‌ترین روش: آدرس استریم را مستقیماً از خود دوربین می‌پرسد.",
    },
    {
        "id": "hikvision",
        "label": "Hikvision",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/Streaming/Channels/{ch}01",
        "sub": "/Streaming/Channels/{ch}02",
        "note": "کانال ۱ → 101 (اصلی) و 102 (فرعی).",
    },
    {
        "id": "dahua",
        "label": "Dahua",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/cam/realmonitor?channel={ch}&subtype=0",
        "sub": "/cam/realmonitor?channel={ch}&subtype=1",
        "note": "subtype=0 اصلی، subtype=1 فرعی.",
    },
    {
        "id": "tiandy",
        "label": "Tiandy",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/Streaming/Channels/{ch}01",
        "sub": "/Streaming/Channels/{ch}02",
        "note": "بیشتر مدل‌های Tiandy سازگار با Hikvision هستند؛ در صورت خطا از ONVIF استفاده کنید.",
    },
    {
        "id": "uniview",
        "label": "Uniview (UNV)",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/media/video1",
        "sub": "/media/video2",
        "note": "",
    },
    {
        "id": "axis",
        "label": "Axis",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/axis-media/media.amp",
        "sub": "/axis-media/media.amp?resolution=640x360",
        "note": "",
    },
    {
        "id": "reolink",
        "label": "Reolink",
        "rtsp_port": 554,
        "onvif_port": 8000,
        "main": "/h264Preview_0{ch}_main",
        "sub": "/h264Preview_0{ch}_sub",
        "note": "پورت ONVIF معمولاً ۸۰۰۰ است.",
    },
    {
        "id": "hanwha",
        "label": "Hanwha / Wisenet (Samsung)",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/profile2/media.smp",
        "sub": "/profile3/media.smp",
        "note": "",
    },
    {
        "id": "vivotek",
        "label": "Vivotek",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/live.sdp",
        "sub": "/live2.sdp",
        "note": "",
    },
    {
        "id": "bosch",
        "label": "Bosch",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/rtsp_tunnel",
        "sub": "/rtsp_tunnel?inst=2",
        "note": "",
    },
    {
        "id": "amcrest",
        "label": "Amcrest",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/cam/realmonitor?channel={ch}&subtype=0",
        "sub": "/cam/realmonitor?channel={ch}&subtype=1",
        "note": "بر پایهٔ Dahua.",
    },
    {
        "id": "ezviz",
        "label": "EZVIZ",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/h264/ch{ch}/main/av_stream",
        "sub": "/h264/ch{ch}/sub/av_stream",
        "note": "بر پایهٔ Hikvision.",
    },
    {
        "id": "tplink_vigi",
        "label": "TP-Link VIGI / Tapo",
        "rtsp_port": 554,
        "onvif_port": 2020,
        "main": "/stream1",
        "sub": "/stream2",
        "note": "نیازمند ساخت «حساب دوربین» در اپ سازنده.",
    },
    {
        "id": "foscam",
        "label": "Foscam",
        "rtsp_port": 554,
        "onvif_port": 888,
        "main": "/videoMain",
        "sub": "/videoSub",
        "note": "",
    },
    {
        "id": "panasonic",
        "label": "Panasonic i-PRO",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/MediaInput/h264",
        "sub": "/MediaInput/h264/stream_2",
        "note": "",
    },
    {
        "id": "generic",
        "label": "سایر برندها (ONVIF عمومی)",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "/onvif1",
        "sub": "/onvif2",
        "note": "اگر کار نکرد، از کشف خودکار ONVIF استفاده کنید.",
    },
    {
        "id": "custom",
        "label": "دستی (آدرس RTSP سفارشی)",
        "rtsp_port": 554,
        "onvif_port": 80,
        "main": "",
        "sub": "",
        "note": "آدرس کامل RTSP را خودتان وارد کنید.",
    },
]

BRANDS_BY_ID = {b["id"]: b for b in CAMERA_BRANDS}


def stream_path(brand_id, channel=1, stream="main"):
    """Render a brand's RTSP path for a channel, or '' if unknown/custom."""
    brand = BRANDS_BY_ID.get(brand_id)
    if not brand:
        return ""
    template = brand.get(stream) or ""
    try:
        return template.format(ch=int(channel))
    except (ValueError, KeyError):
        return template
