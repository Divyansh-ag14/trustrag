class TextParser:
    @staticmethod
    def parse(file_path: str) -> str:
        with open(file_path) as f:
            return f.read().strip()
