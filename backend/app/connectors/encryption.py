"""Fernet encryption for connector credentials."""

import json

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.CONNECTOR_ENCRYPTION_KEY
    if not key:
        raise ValueError(
            "CONNECTOR_ENCRYPTION_KEY not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_credentials(credentials: dict) -> bytes:
    """Encrypt a credentials dict to bytes for DB storage."""
    f = _get_fernet()
    return f.encrypt(json.dumps(credentials).encode())


def decrypt_credentials(encrypted: bytes) -> dict:
    """Decrypt stored bytes back to a credentials dict."""
    f = _get_fernet()
    try:
        return json.loads(f.decrypt(encrypted).decode())
    except InvalidToken:
        raise ValueError("Failed to decrypt credentials — key may have changed")
