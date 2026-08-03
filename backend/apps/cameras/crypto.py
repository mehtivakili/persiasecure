"""
Symmetric encryption for camera credentials at rest (Phase 1, issue #10).

Camera RTSP passwords used to be stored as plaintext database strings. They are
now Fernet‑encrypted (AES‑128‑CBC + HMAC authentication) before they touch the
database and decrypted transparently on read via ``fields.EncryptedCharField``.

Key selection, in order:
  1. ``settings.CREDENTIAL_ENCRYPTION_KEY`` — a real 44‑char urlsafe‑base64 Fernet
     key (recommended for production; generate with ``Fernet.generate_key()``).
  2. Any other non‑empty value of that setting — treated as a passphrase and
     stretched to a Fernet key with SHA‑256.
  3. Fallback: derived from ``settings.SECRET_KEY`` so development works with no
     extra configuration.

IMPORTANT: the key must be **stable and backed up**. If it is lost or changed,
previously stored passwords can no longer be decrypted (they will read back as
their ciphertext and camera authentication will fail until re‑entered). This is
why the encrypted form carries an explicit version prefix — so we can always
tell an encrypted value from a legacy plaintext one during migration.
"""
import base64
import hashlib
import logging
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)

# Marks a value as produced by this module. Any stored value WITHOUT this prefix
# is treated as legacy plaintext (pre‑encryption rows) and returned unchanged —
# it becomes encrypted the next time the record is saved.
PREFIX = "enc:v1:"


def _derive_key(secret) -> bytes:
    """Stretch an arbitrary secret/passphrase into a valid 32‑byte Fernet key."""
    digest = hashlib.sha256(str(secret).encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _fernet():
    from cryptography.fernet import Fernet

    configured = getattr(settings, "CREDENTIAL_ENCRYPTION_KEY", "") or ""
    if configured:
        raw = configured.encode("utf-8") if isinstance(configured, str) else configured
        try:
            # Accept a ready‑made Fernet key as‑is; otherwise treat as passphrase.
            return Fernet(raw)
        except (ValueError, TypeError):
            return Fernet(_derive_key(configured))
    return Fernet(_derive_key(settings.SECRET_KEY))


def encrypt(plaintext) -> str:
    """Return a prefixed ciphertext string, or "" for empty input."""
    if plaintext is None or plaintext == "":
        return ""
    token = _fernet().encrypt(str(plaintext).encode("utf-8")).decode("ascii")
    return PREFIX + token


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def fernet_from_key(key):
    """Build a Fernet from an arbitrary key/passphrase (for key rotation)."""
    from cryptography.fernet import Fernet

    raw = key.encode("utf-8") if isinstance(key, str) else key
    try:
        return Fernet(raw)
    except (ValueError, TypeError):
        return Fernet(_derive_key(key))


def decrypt_with(fernet, value) -> str:
    """Decrypt a prefixed value with a SPECIFIC Fernet (used when rotating keys).
    Legacy (unprefixed) plaintext is returned unchanged."""
    from cryptography.fernet import InvalidToken

    if not value:
        return ""
    if not is_encrypted(value):
        return value
    try:
        return fernet.decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return value


def decrypt(value) -> str:
    """
    Reverse :func:`encrypt`. Legacy (unprefixed) plaintext is returned unchanged
    so the switch to encryption needs no data migration. If a prefixed value
    cannot be decrypted (wrong/rotated key or corruption) the raw stored value is
    returned and a warning is logged rather than raising — a broken key must not
    take the whole cameras API down.
    """
    if not value:
        return ""
    if not is_encrypted(value):
        return value
    from cryptography.fernet import InvalidToken

    token = value[len(PREFIX):].encode("ascii")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        logger.warning("Could not decrypt a stored credential: %s", exc)
        return value
