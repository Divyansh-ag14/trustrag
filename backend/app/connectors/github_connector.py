"""GitHub connector — fetches repo files, wikis, and issues via GitHub REST API."""

import base64

import structlog
import httpx

from app.connectors.base import BaseConnector, FetchedDocument

logger = structlog.get_logger()

GITHUB_API = "https://api.github.com"


class GitHubConnector(BaseConnector):
    """Fetch docs, wikis, and issues from a GitHub repository."""

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.credentials['token']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @property
    def _owner(self) -> str:
        return self.config.get("owner", "")

    @property
    def _repo(self) -> str:
        return self.config.get("repo", "")

    async def test_connection(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{GITHUB_API}/repos/{self._owner}/{self._repo}",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return True, f"Connected to {data['full_name']}"
                if resp.status_code == 404:
                    return False, f"Repository {self._owner}/{self._repo} not found"
                return False, f"GitHub API returned {resp.status_code}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    async def fetch_documents(self) -> list[FetchedDocument]:
        documents = []
        paths = self.config.get("paths", [])
        include_issues = self.config.get("include_issues", False)
        include_wiki = self.config.get("include_wiki", False)

        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch markdown files from specified paths (or root)
            if paths:
                for path in paths:
                    docs = await self._fetch_path(client, path)
                    documents.extend(docs)
            else:
                docs = await self._fetch_path(client, "")
                documents.extend(docs)

            # Fetch issues
            if include_issues:
                issues = await self._fetch_issues(client)
                documents.extend(issues)

            # Fetch wiki
            if include_wiki:
                wiki_docs = await self._fetch_wiki(client)
                documents.extend(wiki_docs)

        logger.info("github.fetch_complete", documents_fetched=len(documents))
        return documents

    async def _fetch_path(self, client: httpx.AsyncClient, path: str) -> list[FetchedDocument]:
        """Recursively fetch markdown files from a repo path."""
        documents = []
        url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}/contents/{path}"

        resp = await client.get(url, headers=self._headers())
        if resp.status_code != 200:
            logger.warning("github.path_fetch_failed", path=path, status=resp.status_code)
            return documents

        data = resp.json()

        # Single file
        if isinstance(data, dict):
            doc = await self._process_file(client, data)
            if doc:
                documents.append(doc)
            return documents

        # Directory listing
        for item in data:
            if item["type"] == "file" and self._is_doc_file(item["name"]):
                doc = await self._process_file(client, item)
                if doc:
                    documents.append(doc)
            elif item["type"] == "dir":
                sub_docs = await self._fetch_path(client, item["path"])
                documents.extend(sub_docs)

        return documents

    async def _process_file(self, client: httpx.AsyncClient, item: dict) -> FetchedDocument | None:
        """Download and process a single file."""
        # Get file content
        if "content" in item and item.get("encoding") == "base64":
            content = base64.b64decode(item["content"]).decode("utf-8", errors="replace")
        else:
            # Fetch content via download_url
            download_url = item.get("download_url")
            if not download_url:
                return None
            resp = await client.get(download_url)
            if resp.status_code != 200:
                return None
            content = resp.text

        if not content.strip():
            return None

        return FetchedDocument(
            title=item.get("name", "Untitled"),
            content=content,
            source_url=item.get("html_url", ""),
            source_type="github",
            content_hash=FetchedDocument.hash_content(content),
            metadata={
                "github_sha": item.get("sha", ""),
                "github_path": item.get("path", ""),
                "owner": self._owner,
                "repo": self._repo,
                "connector_id": str(self.connector.id),
            },
        )

    async def _fetch_issues(self, client: httpx.AsyncClient, max_issues: int = 50) -> list[FetchedDocument]:
        """Fetch open issues with their comments."""
        documents = []
        page = 1

        while len(documents) < max_issues:
            resp = await client.get(
                f"{GITHUB_API}/repos/{self._owner}/{self._repo}/issues",
                headers=self._headers(),
                params={"state": "open", "per_page": 30, "page": page, "sort": "updated"},
            )
            if resp.status_code != 200:
                break

            issues = resp.json()
            if not issues:
                break

            for issue in issues:
                # Skip pull requests (GitHub includes them in issues API)
                if issue.get("pull_request"):
                    continue

                content = f"# {issue['title']}\n\n"
                content += f"**Author:** {issue['user']['login']}\n"
                content += f"**Created:** {issue['created_at']}\n"
                labels = [l["name"] for l in issue.get("labels", [])]
                if labels:
                    content += f"**Labels:** {', '.join(labels)}\n"
                content += f"\n{issue.get('body', '') or ''}\n"

                # Fetch comments
                if issue.get("comments", 0) > 0:
                    comments_resp = await client.get(
                        issue["comments_url"],
                        headers=self._headers(),
                    )
                    if comments_resp.status_code == 200:
                        for comment in comments_resp.json():
                            content += f"\n---\n**{comment['user']['login']}** ({comment['created_at']}):\n"
                            content += f"{comment.get('body', '')}\n"

                documents.append(FetchedDocument(
                    title=f"Issue #{issue['number']}: {issue['title']}",
                    content=content,
                    source_url=issue["html_url"],
                    source_type="github",
                    content_hash=FetchedDocument.hash_content(content),
                    metadata={
                        "github_issue_number": issue["number"],
                        "owner": self._owner,
                        "repo": self._repo,
                        "connector_id": str(self.connector.id),
                        "type": "issue",
                    },
                ))

                if len(documents) >= max_issues:
                    break

            page += 1

        return documents

    async def _fetch_wiki(self, client: httpx.AsyncClient) -> list[FetchedDocument]:
        """Fetch wiki pages from the repo's wiki (if it exists)."""
        # GitHub wiki is a separate git repo at {repo}.wiki.git
        # We can access it via the Contents API on the wiki repo
        wiki_url = f"{GITHUB_API}/repos/{self._owner}/{self._repo}.wiki/contents/"
        resp = await client.get(wiki_url, headers=self._headers())

        if resp.status_code != 200:
            logger.info("github.wiki_not_available", owner=self._owner, repo=self._repo)
            return []

        documents = []
        for item in resp.json():
            if self._is_doc_file(item.get("name", "")):
                doc = await self._process_file(client, item)
                if doc:
                    doc.metadata["type"] = "wiki"
                    documents.append(doc)

        return documents

    @staticmethod
    def _is_doc_file(filename: str) -> bool:
        """Check if a file is a documentation file worth ingesting."""
        lower = filename.lower()
        return lower.endswith((".md", ".mdx", ".txt", ".rst", ".adoc"))
