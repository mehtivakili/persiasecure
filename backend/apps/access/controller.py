"""
Door-controller integration.

This build talks to a generic HTTP relay controller (unlock/lock/status).
OSDP / Wiegand / vendor SDKs plug in here by implementing the same three
functions. All calls degrade gracefully (return False / "offline") so a
controller outage never breaks the API.
"""
import logging

import requests

logger = logging.getLogger(__name__)
TIMEOUT = 4


def unlock(door):
    """Pulse the door relay to unlock for door.unlock_seconds. Returns bool."""
    if not door.controller_url:
        logger.debug("Door %s has no controller_url; simulating unlock.", door.id)
        return True  # simulated success for demos without hardware
    try:
        r = requests.post(
            f"{door.controller_url.rstrip('/')}/relay/{door.relay}/pulse",
            json={"seconds": door.unlock_seconds},
            timeout=TIMEOUT,
        )
        return r.ok
    except requests.RequestException as exc:
        logger.warning("unlock failed for door %s: %s", door.id, exc)
        return False


def lock(door):
    if not door.controller_url:
        return True
    try:
        r = requests.post(
            f"{door.controller_url.rstrip('/')}/relay/{door.relay}/off", timeout=TIMEOUT
        )
        return r.ok
    except requests.RequestException:
        return False


def status(door):
    """Return 'locked' / 'unlocked' / 'offline'."""
    if not door.controller_url:
        return door.state
    try:
        r = requests.get(
            f"{door.controller_url.rstrip('/')}/relay/{door.relay}", timeout=TIMEOUT
        )
        if r.ok:
            return "unlocked" if r.json().get("on") else "locked"
    except requests.RequestException:
        pass
    return "offline"
