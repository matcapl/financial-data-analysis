import fitz
import pytesseract
from pdf2image import convert_from_path
import pandas as pd
import psycopg2
import sys
import os
import re
from datetime import datetime
from utils import hash_datapoint, log_event, get_db_connection, clean_numeric_value, parse_period

class PDFIngester:
    def __init__(self, file_path: str, company_id: int = 1):
        self.file_path = file_path
        self.company_id = company_id
        self.conn = None
        self.ingested_count = 0
        self.skipped_count = 0
        self.error_count = 0

    def __enter__(self):
        self.conn = get_db_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def process_file(self):
        log_event("pdf_ingestion_started", {"file_path": self.file_path, "company_id": self.company_id})
        try:
            doc = fitz.open(self.file_path)
            for page_num in range(len(doc)):
                self._process_page(doc[page_num], page_num + 1)
            doc.close()
            summary = {
                "file_path": self.file_path,
                "ingested_count": self.ingested_count,
                "skipped_count": self.skipped_count,
                "error_count": self.error_count,
                "status": "completed"
            }
            log_event("pdf_ingestion_completed", summary)
            return summary
        except Exception as e:
            log_event("pdf_ingestion_failed", {"file_path": self.file_path, "error": str(e)})
            raise

    def _process_page(self, page, page_num):
        log_event("page_processing_started", {"page_number": page_num})
        try:
            tables = page.find_tables()
            if tables:
                for table_idx, table in enumerate(tables):
                    df = pd.DataFrame(table.extract())
                    self._process_table(df, page_num, table_idx)
            else:
                images = convert_from_path(self.file_path, first_page=page_num, last_page=page_num)
                text = pytesseract.image_to_string(images[0])
                self._process_text(text, page_num)
        except Exception as e:
            self.error_count += 1
            log_event("page_processing_error", {"page_number": page_num, "error": str(e)})

    def _process_table(self, df, page_num, table_idx):
        df.columns = [str(col).strip().lower() for col in df.columns]
        for _, row in df.iterrows():
            row_label = str(row.iloc[0]).strip().lower() if len(row) > 0 else ""
            metric = self._identify_metric(row_label)
            if not metric:
                continue
            for col in df.columns[1:]:
                value = clean_numeric_value(row.get(col))
                if value is None:
                    self.skipped_count += 1
                    log_event("value_skipped", {"reason": "Non-numeric value", "column": col})
                    continue
                period_info = parse_period(col, "Monthly")
                self._insert_metric(metric, period_info, value, page_num, f"Table {table_idx + 1}")

    def _process_text(self, text, page_num):
        lines = text.split("\n")
        for line_idx, line in enumerate(lines):
            line = line.strip().lower()
            if not line:
                continue
            metric = self._identify_metric(line)
            if not metric:
                continue
            numbers = re.findall(r'-?[\d,]+\.?\d*', line)
            for num_str in numbers:
                value = clean_numeric_value(num_str)
                if value is None:
                    continue
                period_info = parse_period("Feb 2025" if "feb" in line else "Unknown", "Monthly")
                self._insert_metric(metric, period_info, value, page_num, f"Text line {line_idx + 1}")

    def _identify_metric(self, text):
        if "revenue" in text and "gross" not in text:
            return "Revenue"
        if "gross profit" in text or "gross margin" in text:
            return "Gross Profit"
        if "ebitda" in text:
            return "EBITDA"
        return None

    def _insert_metric(self, metric, period_info, value, page_num, source_detail):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id FROM line_item_definitions WHERE name = %s", (metric,))
                line_item_id = cur.fetchone()
                if not line_item_id:
                    self.error_count += 1
                    log_event("line_item_not_found", {"line_item": metric})
                    return
                line_item_id = line_item_id[0]

                cur.execute(
                    "SELECT id FROM periods WHERE period_type = %s AND period_label = %s",
                    (period_info["type"], period_info["label"])
                )
                period = cur.fetchone()
                if not period:
                    cur.execute(
                        "INSERT INTO periods (period_type, period_label, start_date, end_date, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                        (period_info["type"], period_info["label"], period_info["start_date"], period_info["end_date"], datetime.now(), datetime.now())
                    )
                    period_id = cur.fetchone()[0]
                else:
                    period_id = period[0]

                data = {
                    "company_id": self.company_id,
                    "period_id": period_id,
                    "line_item_id": line_item_id,
                    "value_type": "Actual",
                    "frequency": period_info["type"],
                    "value": value,
                    "currency": "USD",
                    "source_file": os.path.basename(self.file_path),
                    "source_page": page_num,
                    "source_type": "Raw",
                    "notes": f"Extracted from PDF: {source_detail}"
                }
                data["hash"] = hash_datapoint(data["company_id"], data["period_id"], metric, data["value_type"], data["frequency"])
                cur.execute("SELECT id FROM financial_metrics WHERE hash = %s", (data["hash"],))
                if cur.fetchone():
                    self.skipped_count += 1
                    log_event("duplicate_skipped", {"hash": data["hash"]})
                    return
                cur.execute(
                    """INSERT INTO financial_metrics (
                        company_id, period_id, line_item_id, value_type, frequency, value, currency,
                        source_file, source_page, source_type, notes, hash, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        data["company_id"], data["period_id"], data["line_item_id"], data["value_type"],
                        data["frequency"], data["value"], data["currency"], data["source_file"],
                        data["source_page"], data["source_type"], data["notes"], data["hash"],
                        datetime.now(), datetime.now()
                    )
                )
                self.ingested_count += 1
                log_event("metric_inserted", {"line_item": metric, "period_label": period_info["label"], "value": value})
        except Exception as e:
            self.error_count += 1
            log_event("insert_error", {"error": str(e), "metric": metric})

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_pdf.py <pdf_file_path> [company_id]")
        sys.exit(1)
    file_path = sys.argv[1]
    company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    with PDFIngester(file_path, company_id) as ingester:
        result = ingester.process_file()
        print(f"Ingestion result: {result}")