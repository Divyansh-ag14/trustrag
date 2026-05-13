import fitz


class PDFParser:
    @staticmethod
    def parse(file_path: str) -> str:
        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text)
        doc.close()
        return "\n\n".join(pages)
