"""Tests for the rate-limit middleware key derivation and per-user isolation.

Regression target: the limiter used to key on the JWT prefix (`auth[7:15]`),
but every HS256 token shares the same header prefix, so all authenticated users
collapsed into a single global bucket. The key must be the user id.
"""

import uuid
from types import SimpleNamespace

from starlette.responses import Response

from app.api.middleware import RateLimitMiddleware
from app.services.auth_service import create_access_token


def _token(user_id: uuid.UUID, workspace_id: uuid.UUID | None = None) -> str:
    return create_access_token(user_id, workspace_id or uuid.uuid4())


def _request(path: str = "/api/v1/chat/query", token: str | None = None, host: str = "1.2.3.4"):
    headers = {}
    if token is not None:
        headers["authorization"] = f"Bearer {token}"
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        headers=headers,
        client=SimpleNamespace(host=host),
    )


async def _ok_next(_request):
    return Response("ok")


class TestClientKey:
    def setup_method(self):
        self.mw = RateLimitMiddleware(None, max_requests=60, window_seconds=60)

    def test_different_users_get_different_buckets(self):
        # The core bug: two distinct users must not share a key.
        key_a = self.mw._get_client_key(_request(token=_token(uuid.uuid4())))
        key_b = self.mw._get_client_key(_request(token=_token(uuid.uuid4())))
        assert key_a != key_b
        assert key_a.startswith("user:")
        assert key_b.startswith("user:")

    def test_same_user_same_bucket(self):
        uid = uuid.uuid4()
        key1 = self.mw._get_client_key(_request(token=_token(uid)))
        key2 = self.mw._get_client_key(_request(token=_token(uid)))
        assert key1 == key2 == f"user:{uid}"

    def test_invalid_token_falls_back_to_ip(self):
        key = self.mw._get_client_key(_request(token="not-a-real-jwt"))
        assert key == "ip:1.2.3.4"

    def test_no_auth_uses_ip(self):
        key = self.mw._get_client_key(_request(token=None))
        assert key == "ip:1.2.3.4"

    def test_non_api_path_not_limited(self):
        key = self.mw._get_client_key(_request(path="/health", token=_token(uuid.uuid4())))
        assert key is None


class TestEnforcement:
    async def test_limit_enforced_for_a_user(self):
        mw = RateLimitMiddleware(None, max_requests=3, window_seconds=60)
        req = _request(token=_token(uuid.uuid4()))

        for _ in range(3):
            resp = await mw.dispatch(req, _ok_next)
            assert resp.status_code == 200

        # 4th request in the window is over the limit
        resp = await mw.dispatch(req, _ok_next)
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    async def test_one_user_exhausting_limit_does_not_block_another(self):
        # This is exactly what the old global-bucket bug broke.
        mw = RateLimitMiddleware(None, max_requests=3, window_seconds=60)
        req_a = _request(token=_token(uuid.uuid4()))
        req_b = _request(token=_token(uuid.uuid4()))

        for _ in range(4):
            await mw.dispatch(req_a, _ok_next)

        # User A is now rate-limited; user B must still be served.
        resp_b = await mw.dispatch(req_b, _ok_next)
        assert resp_b.status_code == 200

    async def test_separate_ips_isolated(self):
        mw = RateLimitMiddleware(None, max_requests=2, window_seconds=60)
        req_1 = _request(token=None, host="10.0.0.1")
        req_2 = _request(token=None, host="10.0.0.2")

        for _ in range(3):
            await mw.dispatch(req_1, _ok_next)

        resp_2 = await mw.dispatch(req_2, _ok_next)
        assert resp_2.status_code == 200
