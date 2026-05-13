import csv


class CSVParser:
    @staticmethod
    def parse(file_path: str) -> str:
        rows = []
        with open(file_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                parts = [f"{k}: {v}" for k, v in row.items() if v and v.strip()]
                rows.append(" | ".join(parts))
        return "\n\n".join(rows)
