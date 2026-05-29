"""Web scraper connector — crawls a website and extracts content."""

import asyncio
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import structlog
import httpx
from bs4 import BeautifulSoup

from app.connectors.base import BaseConnector, FetchedDocument

logger = structlog.get_logger()


class WebScraperConnector(BaseConnector):
    """Crawl a website and extract page content for ingestion."""

    async def test_connection(self) -> tuple[bool, str]:
        base_url = self.config.get("base_url", "")
        if not base_url:
            return False, "No base_url configured"

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(base_url)
                if resp.status_code == 200:
                    return True, f"Successfully reached {base_url}"
                return False, f"Got status {resp.status_code} for {base_url}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    async def fetch_documents(self) -> list[FetchedDocument]:
        base_url = self.config.get("base_url", "")
        max_depth = self.config.get("max_depth", 2)
        max_pages = self.config.get("max_pages", 50)
        css_selector = self.config.get("css_selector", "article, main, .content")
        exclude_patterns = self.config.get("exclude_patterns", [])

        if not base_url:
            return []

        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc

        # Check robots.txt
        robot_parser = self._load_robots(base_url)

        visited: set[str] = set()
        documents: list[FetchedDocument] = []
        queue: list[tuple[str, int]] = [(base_url, 0)]

        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "TrustRAG-Crawler/1.0"},
        ) as client:
            while queue and len(documents) < max_pages:
                url, depth = queue.pop(0)

                # Normalize URL
                url = url.split("#")[0].rstrip("/")
                if url in visited:
                    continue

                # Check exclusions
                if any(pattern in url for pattern in exclude_patterns):
                    continue

                # Check robots.txt
                if robot_parser and not robot_parser.can_fetch("TrustRAG-Crawler", url):
                    continue

                visited.add(url)

                try:
                    # Rate limit: 1 req/sec
                    await asyncio.sleep(1.0)

                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue

                    content_type = resp.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        continue

                    html = resp.text
                    soup = BeautifulSoup(html, "html.parser")

                    # Extract content
                    text = self._extract_content(soup, css_selector)
                    title = self._extract_title(soup, url)

                    if text and len(text.strip()) > 100:
                        images = self._extract_images(soup, url)

                        documents.append(FetchedDocument(
                            title=title,
                            content=text,
                            source_url=url,
                            source_type="web",
                            content_hash=FetchedDocument.hash_content(text),
                            metadata={
                                "crawl_depth": depth,
                                "base_url": base_url,
                                "connector_id": str(self.connector.id),
                            },
                            images=images,
                        ))

                    # Discover links for further crawling
                    if depth < max_depth:
                        for link in soup.find_all("a", href=True):
                            href = link["href"]
                            full_url = urljoin(url, href)
                            parsed = urlparse(full_url)

                            # Only follow same-domain links
                            if parsed.netloc == base_domain:
                                clean_url = full_url.split("#")[0].rstrip("/")
                                if clean_url not in visited:
                                    queue.append((clean_url, depth + 1))

                except Exception as e:
                    logger.warning("web_scraper.page_failed", url=url, error=str(e))

        logger.info("web_scraper.crawl_complete", pages_crawled=len(documents), urls_visited=len(visited))
        return documents

    @staticmethod
    def _load_robots(base_url: str) -> RobotFileParser | None:
        """Load and parse robots.txt for the site."""
        try:
            parsed = urlparse(base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            return rp
        except Exception:
            return None

    @staticmethod
    def _extract_content(soup: BeautifulSoup, css_selector: str) -> str:
        """Extract main content from HTML page."""
        # Remove unwanted elements
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        # Try CSS selector first
        content_elements = soup.select(css_selector)
        if content_elements:
            text_parts = []
            for elem in content_elements:
                text_parts.append(elem.get_text(separator="\n", strip=True))
            return "\n\n".join(text_parts)

        # Fallback: get body text
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)

        return soup.get_text(separator="\n", strip=True)

    @staticmethod
    def _extract_title(soup: BeautifulSoup, url: str) -> str:
        """Extract page title."""
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return urlparse(url).path.split("/")[-1] or "Untitled"

    @staticmethod
    def _extract_images(soup: BeautifulSoup, page_url: str) -> list[dict]:
        """Extract meaningful images from the page."""
        images = []
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if not src:
                continue

            # Skip tiny icons and tracking pixels
            width = img.get("width", "")
            height = img.get("height", "")
            try:
                if width and int(width) < 50:
                    continue
                if height and int(height) < 50:
                    continue
            except (ValueError, TypeError):
                pass

            full_url = urljoin(page_url, src)
            alt = img.get("alt", "")

            # Skip images with no alt text and no meaningful filename
            if not alt and "logo" not in src.lower() and "icon" not in src.lower():
                images.append({"url": full_url, "alt": alt, "data": None})

        return images[:20]  # Cap at 20 images per page
