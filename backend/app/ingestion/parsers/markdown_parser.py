import re


class MarkdownParser:
    @staticmethod
    def parse(file_path: str) -> str:
        with open(file_path) as f:
            content = f.read()

        content = re.sub(r"```[\s\S]*?```", lambda m: m.group(0), content)
        content = re.sub(r"!\[.*?\]\(.*?\)", "", content)
        content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)

        return content.strip()
