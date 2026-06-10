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


# --- Fake async Redis (sorted-set sliding window) for hermetic enforcement tests ---
class _FakePipeline:
    def __init__(self, store):
        self._store = store
        self._ops = []

    def zremrangebyscore(self, key, mn, mx):
        self._ops.append(("zrem", key, mn, mx))
        return self

    def zadd(self, key, mapping):
        self._ops.append(("zadd", key, mapping))
        return self

    def zcard(self, key):
        self._ops.append(("zcard", key))
        return self

    def expire(self, key, ttl):
        self._ops.append(("expire", key, ttl))
        return self

    async def execute(self):
        return [self._store._apply(op) for op in self._ops]


class _FakeAsyncRedis:
    def __init__(self):
        self.data: dict[str, dict[str, float]] = {}

    def pipeline(self):
        return _FakePipeline(self)

    def _apply(self, op):
        kind = op[0]
        if kind == "zrem":
            _, key, mn, mx = op
            d = self.data.get(key, {})
            removed = [m for m, s in d.items() if mn <= s <= mx]
            for m in removed:
                del d[m]
            return len(removed)
        if kind == "zadd":
            _, key, mapping = op
            self.data.setdefault(key, {}).update(mapping)
            return len(mapping)
        if kind == "zcard":
            return len(self.data.get(op[1], {}))
        return True  # expire

    async def zrange(self, key, start, stop, withscores=False):
        items = sorted(self.data.get(key, {}).items(), key=lambda kv: kv[1])
        sel = items[start:] if stop == -1 else items[start:stop + 1]
        return sel if withscores else [m for m, _ in sel]


def _mw(max_requests: int) -> RateLimitMiddleware:
    mw = RateLimitMiddleware(None, max_requests=max_requests, window_seconds=60)
    mw._redis = _FakeAsyncRedis()
    return mw


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
        mw = _mw(3)
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
        mw = _mw(3)
        req_a = _request(token=_token(uuid.uuid4()))
        req_b = _request(token=_token(uuid.uuid4()))

        for _ in range(4):
            await mw.dispatch(req_a, _ok_next)

        # User A is now rate-limited; user B must still be served.
        resp_b = await mw.dispatch(req_b, _ok_next)
        assert resp_b.status_code == 200

    async def test_separate_ips_isolated(self):
        mw = _mw(2)
        req_1 = _request(token=None, host="10.0.0.1")
        req_2 = _request(token=None, host="10.0.0.2")

        for _ in range(3):
            await mw.dispatch(req_1, _ok_next)

        resp_2 = await mw.dispatch(req_2, _ok_next)
        assert resp_2.status_code == 200

    async def test_fails_open_when_redis_unavailable(self):
        # If Redis is down the limiter must not take the API down with it.
        class _BrokenRedis:
            def pipeline(self):
                raise ConnectionError("redis down")

        mw = _mw(1)
        mw._redis = _BrokenRedis()
        req = _request(token=_token(uuid.uuid4()))
        for _ in range(5):  # well over the limit of 1
            resp = await mw.dispatch(req, _ok_next)
            assert resp.status_code == 200
