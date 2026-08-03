"""
SMS / voice-call notification service.

Config resolution order (per organization):
  1. NotificationSettings row for the org (edited in the Settings panel)
  2. settings.NOTIFY from environment (.env) as a fallback / default
Providers: console (log only, no account) | kavenegar (Iran) | twilio.

Both send functions return True/False and never raise, so a provider outage
can't break the automation executor.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 10


def env_conf():
    return getattr(settings, "NOTIFY", {}) or {}


def org_conf(organization):
    """
    Merge the org's saved NotificationSettings over the env defaults.
    Returns a dict with normalized UPPER keys used by send_sms/voice_call.
    """
    conf = dict(env_conf())
    if organization is None:
        return conf
    try:
        ns = organization.notification_settings
    except Exception:
        return conf
    if not ns:
        return conf
    # Only override when the DB value is set (non-empty), so a blank field
    # keeps the env default rather than wiping it.
    mapping = {
        "PROVIDER": ns.provider,
        "KAVENEGAR_API_KEY": ns.kavenegar_api_key,
        "SMS_SENDER": ns.sms_sender,
        "TWILIO_ACCOUNT_SID": ns.twilio_sid,
        "TWILIO_AUTH_TOKEN": ns.twilio_token,
        "TWILIO_FROM": ns.twilio_from,
    }
    for k, v in mapping.items():
        if v:
            conf[k] = v
    conf["_recipients"] = ns.recipients or []
    return conf


def recipients(organization, channel="sms"):
    """Phone numbers configured to receive `channel` (sms|call) for the org."""
    try:
        ns = organization.notification_settings
    except Exception:
        return []
    if not ns:
        return []
    key = "sms" if channel == "sms" else "call"
    return [
        r["phone"]
        for r in (ns.recipients or [])
        if r.get("phone") and r.get("active", True) and r.get(key, True)
    ]


def send_sms(phone, message, conf=None):
    conf = conf or env_conf()
    provider = conf.get("PROVIDER", "console")
    try:
        if provider == "kavenegar":
            r = requests.get(
                f"https://api.kavenegar.com/v1/{conf['KAVENEGAR_API_KEY']}/sms/send.json",
                params={
                    "receptor": phone,
                    "message": message,
                    **({"sender": conf["SMS_SENDER"]} if conf.get("SMS_SENDER") else {}),
                },
                timeout=TIMEOUT,
            )
            ok = r.status_code == 200
        elif provider == "twilio":
            sid = conf["TWILIO_ACCOUNT_SID"]
            r = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=(sid, conf["TWILIO_AUTH_TOKEN"]),
                data={"To": phone, "From": conf.get("TWILIO_FROM", ""), "Body": message},
                timeout=TIMEOUT,
            )
            ok = r.status_code in (200, 201)
        else:  # console
            logger.warning("[SMS→%s] %s", phone, message)
            ok = True
        logger.info("send_sms provider=%s to=%s ok=%s", provider, phone, ok)
        return ok
    except Exception as exc:
        logger.error("send_sms failed (%s): %s", provider, exc)
        return False


def voice_call(phone, message, conf=None):
    """Text-to-speech phone call reading the alarm message."""
    conf = conf or env_conf()
    provider = conf.get("PROVIDER", "console")
    try:
        if provider == "kavenegar":
            r = requests.get(
                f"https://api.kavenegar.com/v1/{conf['KAVENEGAR_API_KEY']}/call/maketts.json",
                params={"receptor": phone, "message": message},
                timeout=TIMEOUT,
            )
            ok = r.status_code == 200
        elif provider == "twilio":
            sid = conf["TWILIO_ACCOUNT_SID"]
            twiml = f'<Response><Say language="en-US">{message}</Say></Response>'
            r = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
                auth=(sid, conf["TWILIO_AUTH_TOKEN"]),
                data={"To": phone, "From": conf.get("TWILIO_FROM", ""), "Twiml": twiml},
                timeout=TIMEOUT,
            )
            ok = r.status_code in (200, 201)
        else:  # console
            logger.warning("[CALL→%s] %s", phone, message)
            ok = True
        logger.info("voice_call provider=%s to=%s ok=%s", provider, phone, ok)
        return ok
    except Exception as exc:
        logger.error("voice_call failed (%s): %s", provider, exc)
        return False
