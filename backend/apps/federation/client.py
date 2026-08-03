"""Client for talking to a remote PersianSecure node's REST API."""
import logging

import requests

logger = logging.getLogger(__name__)
TIMEOUT = 8


def _token(server):
    try:
        r = requests.post(
            f"{server.base_url.rstrip('/')}/api/auth/token/",
            json={"username": server.username, "password": server.password},
            timeout=TIMEOUT,
        )
        if r.ok:
            return r.json().get("access")
    except requests.RequestException as exc:
        logger.warning("federation login failed for %s: %s", server.name, exc)
    return None


def fetch_cameras(server):
    """Return a list of remote camera dicts, or None on failure."""
    token = _token(server)
    if not token:
        return None
    try:
        r = requests.get(
            f"{server.base_url.rstrip('/')}/api/cameras/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        if r.ok:
            data = r.json()
            return data.get("results", data) if isinstance(data, dict) else data
    except requests.RequestException as exc:
        logger.warning("federation fetch failed for %s: %s", server.name, exc)
    return None


def ping(server):
    try:
        r = requests.get(f"{server.base_url.rstrip('/')}/api/health", timeout=TIMEOUT)
        return r.ok
    except requests.RequestException:
        return False
