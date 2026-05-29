"""Passthrough parser for GitHub content.

GitHub connector fetches and converts content to markdown before writing
to disk, so this parser just reads the file.
"""


class GitHubParser:
    @staticmethod
    def parse(file_path: str) -> str:
        with open(file_path, encoding="utf-8") as f:
            return f.read().strip()
