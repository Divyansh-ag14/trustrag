from app.ingestion.parsers.csv_parser import CSVParser
from app.ingestion.parsers.faq_parser import FAQParser
from app.ingestion.parsers.github_parser import GitHubParser
from app.ingestion.parsers.html_parser import HTMLParser
from app.ingestion.parsers.markdown_parser import MarkdownParser
from app.ingestion.parsers.notion_parser import NotionParser
from app.ingestion.parsers.pdf_parser import PDFParser
from app.ingestion.parsers.slack_parser import SlackParser
from app.ingestion.parsers.text_parser import TextParser
from app.ingestion.parsers.web_parser import WebParser

PARSERS = {
    "pdf": PDFParser,
    "markdown": MarkdownParser,
    "text": TextParser,
    "html": HTMLParser,
    "csv": CSVParser,
    "faq": FAQParser,
    "slack_export": SlackParser,
    "notion": NotionParser,
    "github": GitHubParser,
    "web": WebParser,
}

__all__ = [
    "PARSERS", "PDFParser", "MarkdownParser", "TextParser",
    "HTMLParser", "CSVParser", "FAQParser", "SlackParser",
    "NotionParser", "GitHubParser", "WebParser",
]
