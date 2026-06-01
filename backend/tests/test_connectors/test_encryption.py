"""Tests for connector credential encryption."""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.connectors.encryption import encrypt_credentials, decrypt_credentials


@pytest.fixture
def fernet_key():
    return Fernet.generate_key().decode()


class TestEncryption:
    def test_round_trip(self, fernet_key):
        creds = {"token": "secret-abc-123", "extra": "value"}
        with patch("app.connectors.encryption.settings") as mock_settings:
            mock_settings.CONNECTOR_ENCRYPTION_KEY = fernet_key
            encrypted = encrypt_credentials(creds)
            assert isinstance(encrypted, bytes)
            assert b"secret" not in encrypted

            decrypted = decrypt_credentials(encrypted)
            assert decrypted == creds

    def test_different_keys_fail(self, fernet_key):
        creds = {"token": "my-secret"}
        with patch("app.connectors.encryption.settings") as mock_settings:
            mock_settings.CONNECTOR_ENCRYPTION_KEY = fernet_key
            encrypted = encrypt_credentials(creds)

        other_key = Fernet.generate_key().decode()
        with patch("app.connectors.encryption.settings") as mock_settings:
            mock_settings.CONNECTOR_ENCRYPTION_KEY = other_key
            with pytest.raises(ValueError, match="decrypt"):
                decrypt_credentials(encrypted)

    def test_missing_key_raises(self):
        with patch("app.connectors.encryption.settings") as mock_settings:
            mock_settings.CONNECTOR_ENCRYPTION_KEY = ""
            with pytest.raises(ValueError, match="CONNECTOR_ENCRYPTION_KEY"):
                encrypt_credentials({"token": "x"})

    def test_empty_credentials(self, fernet_key):
        with patch("app.connectors.encryption.settings") as mock_settings:
            mock_settings.CONNECTOR_ENCRYPTION_KEY = fernet_key
            encrypted = encrypt_credentials({})
            decrypted = decrypt_credentials(encrypted)
            assert decrypted == {}

    def test_complex_credentials(self, fernet_key):
        creds = {
            "token": "ghp_abc123",
            "refresh_token": "rt_xyz",
            "nested": {"a": 1, "b": [1, 2, 3]},
        }
        with patch("app.connectors.encryption.settings") as mock_settings:
            mock_settings.CONNECTOR_ENCRYPTION_KEY = fernet_key
            encrypted = encrypt_credentials(creds)
            decrypted = decrypt_credentials(encrypted)
            assert decrypted == creds
