"""Passthrough parser for Notion content.

Notion connector converts blocks to markdown before writing to disk,
so this parser just reads the file.
"""


class NotionParser:
    @staticmethod
    def parse(file_path: str) -> str:
        with open(file_path, encoding="utf-8") as f:
            return f.read().strip()
