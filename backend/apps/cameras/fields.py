"""Custom model fields for the cameras app."""
from django.db import models

from . import crypto


class EncryptedCharField(models.CharField):
    """
    A CharField whose value is Fernet‑encrypted at rest.

    In Python the attribute is always the plaintext string; only the database
    column holds ciphertext. Existing plaintext rows are read back unchanged
    (see :func:`crypto.decrypt`) and are re‑written encrypted on the next save,
    so no data migration is required. ``max_length`` must be large enough to
    hold the ciphertext (a short secret expands to ~130 chars).
    """

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return crypto.decrypt(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        # Avoid double‑encrypting an already‑encrypted value.
        if crypto.is_encrypted(value):
            return value
        return crypto.encrypt(value)
