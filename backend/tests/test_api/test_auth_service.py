"""Unit tests for auth service — password hashing, JWT, slugify."""

import uuid

from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    slugify,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "secure_password_123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """bcrypt uses random salt, so same password produces different hashes."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2  # different salts
        assert verify_password("same_password", h1) is True
        assert verify_password("same_password", h2) is True


class TestJWT:
    def test_access_token_roundtrip(self):
        user_id = uuid.uuid4()
        ws_id = uuid.uuid4()
        token = create_access_token(user_id, ws_id)
        payload = decode_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["workspace_id"] == str(ws_id)
        assert payload["type"] == "access"

    def test_refresh_token_roundtrip(self):
        user_id = uuid.uuid4()
        ws_id = uuid.uuid4()
        token = create_refresh_token(user_id, ws_id)
        payload = decode_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_invalid_token_returns_empty(self):
        payload = decode_token("garbage.not.a.token")
        assert payload == {}

    def test_access_and_refresh_are_different(self):
        uid = uuid.uuid4()
        wsid = uuid.uuid4()
        access = create_access_token(uid, wsid)
        refresh = create_refresh_token(uid, wsid)
        assert access != refresh


class TestSlugify:
    def test_basic(self):
        assert slugify("My Company") == "my-company"

    def test_special_chars(self):
        result = slugify("Acme! Corp. #1")
        assert result == "acme-corp-1"

    def test_extra_whitespace(self):
        assert slugify("  hello   world  ") == "hello-world"

    def test_truncation(self):
        long_name = "a" * 200
        result = slugify(long_name)
        assert len(result) <= 100

    def test_unicode(self):
        result = slugify("Über Corp")
        assert len(result) > 0
