"""Tests for connector input hardening found during live testing.

- Notion: accept a pasted page/DB URL (not just the raw id).
- GitHub: _fetch_issues uses the Search API (items[] shape) and excludes PRs.
"""

from types import SimpleNamespace

from app.connectors.github_connector import GitHubConnector
from app.connectors.notion_connector import _normalize_notion_id


class TestNormalizeNotionId:
    def test_app_notion_url(self):
        url = "https://app.notion.com/p/TrustRAG-Test-Onboarding-Guide-376d829e528a800b846cdd684db097cd?source=copy_link"
        assert _normalize_notion_id(url) == "376d829e528a800b846cdd684db097cd"

    def test_www_notion_url_with_query(self):
        url = "https://www.notion.so/My-Page-1a2b3c4d5e6f7080abcd1234567890ef?pvs=4"
        assert _normalize_notion_id(url) == "1a2b3c4d5e6f7080abcd1234567890ef"

    def test_dashed_uuid_preserved(self):
        uid = "1a2b3c4d-5e6f-7080-abcd-1234567890ef"
        assert _normalize_notion_id(uid) == uid

    def test_raw_id_passthrough(self):
        uid = "376d829e528a800b846cdd684db097cd"
        assert _normalize_notion_id(uid) == uid

    def test_strips_surrounding_whitespace(self):
        assert _normalize_notion_id("  \t376d829e528a800b846cdd684db097cd \n") == "376d829e528a800b846cdd684db097cd"

    def test_non_id_passthrough(self):
        # No id present — return as-is (let the API surface the error).
        assert _normalize_notion_id("not-an-id") == "not-an-id"


# --- GitHub issues via Search API -------------------------------------------

class _FakeResp:
    def __init__(self, status, data):
        self.status_code = status
        self._data = data

    def json(self):
        return self._data


class _FakeClient:
    """Minimal async stand-in for httpx.AsyncClient used by _fetch_issues."""

    def __init__(self, pages: list[list[dict]]):
        self._pages = pages  # one list of search items per page (1-indexed)

    async def get(self, url, headers=None, params=None):
        if "/search/issues" in url:
            page = (params or {}).get("page", 1)
            items = self._pages[page - 1] if page - 1 < len(self._pages) else []
            return _FakeResp(200, {"items": items})
        # comments_url
        return _FakeResp(200, [])


def _issue(number: int, is_pr: bool = False, comments: int = 0) -> dict:
    d = {
        "number": number,
        "title": f"Issue {number}",
        "user": {"login": "octocat"},
        "created_at": "2025-01-01T00:00:00Z",
        "labels": [{"name": "bug"}],
        "body": f"body of {number}",
        "comments": comments,
        "comments_url": f"https://api.github.com/issues/{number}/comments",
        "html_url": f"https://github.com/o/r/issues/{number}",
    }
    if is_pr:
        d["pull_request"] = {"url": "..."}
    return d


def _connector() -> GitHubConnector:
    model = SimpleNamespace(id="cid", config={"owner": "o", "repo": "r"})
    return GitHubConnector(model, {})


class TestFetchIssues:
    async def test_parses_search_items(self):
        client = _FakeClient(pages=[[_issue(1), _issue(2)]])
        docs = await _connector()._fetch_issues(client, max_issues=50)
        assert len(docs) == 2
        assert docs[0].title == "Issue #1: Issue 1"
        assert docs[0].source_type == "github"

    async def test_excludes_pull_requests(self):
        client = _FakeClient(pages=[[_issue(1), _issue(2, is_pr=True), _issue(3)]])
        docs = await _connector()._fetch_issues(client, max_issues=50)
        titles = [d.title for d in docs]
        assert len(docs) == 2
        assert "Issue #2: Issue 2" not in titles

    async def test_respects_max_issues(self):
        client = _FakeClient(pages=[[_issue(i) for i in range(30)], [_issue(i) for i in range(30, 60)]])
        docs = await _connector()._fetch_issues(client, max_issues=5)
        assert len(docs) == 5

    async def test_stops_on_last_partial_page(self):
        # One short page (< per_page) → should stop, not loop forever.
        client = _FakeClient(pages=[[_issue(1), _issue(2)]])
        docs = await _connector()._fetch_issues(client, max_issues=50)
        assert len(docs) == 2
