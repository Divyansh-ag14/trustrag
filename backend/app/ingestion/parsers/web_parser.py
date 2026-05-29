"""Passthrough parser for web-scraped content.

Web scraper connector extracts and cleans HTML content before writing
to disk, so this parser just reads the file.
"""


class WebParser:
    @staticmethod
    def parse(file_path: str) -> str:
        with open(file_path, encoding="utf-8") as f:
            return f.read().strip()
