from app.ingestion.parsers.csv_parser import CSVParser
from app.ingestion.parsers.html_parser import HTMLParser
from app.ingestion.parsers.markdown_parser import MarkdownParser
from app.ingestion.parsers.pdf_parser import PDFParser
from app.ingestion.parsers.text_parser import TextParser

PARSERS = {
    "pdf": PDFParser,
    "markdown": MarkdownParser,
    "text": TextParser,
    "html": HTMLParser,
    "csv": CSVParser,
}

__all__ = ["PARSERS", "PDFParser", "MarkdownParser", "TextParser", "HTMLParser", "CSVParser"]
