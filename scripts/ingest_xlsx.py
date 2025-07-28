import pandas as pd
import psycopg2
import sys
import os
from utils import hash_datapoint, log_event, get_db_connection, clean_numeric_value, parse_period

class XLSXIngester:
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
        log_event("ingestion_started", {"file_path": self.file_path, "company_id": self.company_id})
        try:
            df = pd.read_excel(self.file_path, sheet_name=0)
            df.columns = [col.lower().strip() for col in df.columns]
            for _, row in df.iterrows():
                self._process_row(row)
            self.conn.commit()
            summary = {
                "file_path": self.file_path,
                "ingested_count": self.ingested_count,
                "skipped_count": self.skipped_count,
                "error_count": self.error_count,
                "status": "completed"
            }
            log_event("ingestion_completed", summary)
            return summary
        except Exception as e:
            log_event("ingestion_failed", {"file_path": self.file_path, "error": str(e)})
            raise

    def _process_row(self, row):
        try:
            if pd.isna(row.get("line_item")) or pd.isna(row.get("period_label")):
                self.skipped_count += 1
                log_event("row_skipped", {"reason": "Missing line_item or period_label"})
                return
            line_item = str(row["line_item"]).strip()
            if line_item not in ["Revenue", "Gross Profit", "EBITDA"]:
                self.skipped_count += 1
                log_event("row_skipped", {"reason": f"Invalid line_item: {line_item}"})
                return

            period_info = parse_period(row["period_label"], row.get("period_type", "Monthly"))
            with self.conn.cursor() as cur:
                cur.execute("SELECT id FROM line_item_definitions WHERE name = %s", (line_item,))
                line_item_id = cur.fetchone()
                if not line_item_id:
                    self.error_count += 1
                    log_event("line_item_not_found", {"line_item": line_item})
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
                    "value_type": row.get("value_type", "Actual"),
                    "frequency": period_info["type"],
                    "value": clean_numeric_value(row.get("value")),
                    "currency": row.get("currency", "USD"),
                    "source_file": os.path.basename(self.file_path),
                    "source_page": row.get("source_page", "Sheet1"),
                    "source_type": "Raw",
                    "notes": row.get("notes", "")
                }
                data["hash"] = hash_datapoint(data["company_id"], data["period_id"], line_item, data["value_type"], data["frequency"])
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
                log_event("metric_inserted", {"line_item": line_item, "period_label": period_info["label"], "value": data["value"]})
        except Exception as e:
            self.error_count += 1
            log_event("row_processing_error", {"error": str(e), "row": row.to_dict()})

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_xlsx.py <excel_file_path> [company_id]")
        sys.exit(1)
    file_path = sys.argv[1]
    company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    with XLSXIngester(file_path, company_id) as ingester:
        result = ingester.process_file()
        print(f"Ingestion result: {result}")