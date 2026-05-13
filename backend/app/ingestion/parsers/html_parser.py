from bs4 import BeautifulSoup


class HTMLParser:
    @staticmethod
    def parse(file_path: str) -> str:
        with open(file_path) as f:
            html = f.read()

        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
