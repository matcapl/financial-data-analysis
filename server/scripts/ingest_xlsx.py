# server/scripts/ingest_xlsx.py

import pandas as pd
from datetime import datetime
import psycopg2
import sys
import os
from utils import (
    hash_datapoint, log_event, get_db_connection,
    clean_numeric_value, parse_period
)
from field_mapper import map_and_filter_row


class XLSXIngester:
    def __init__(self, file_path: str, company_id: int = 1):
        self.file_path = file_path
        self.company_id = company_id
        self.conn = None
        self.ingested_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.current_file_hashes = set()

    def __enter__(self):
        self.conn = get_db_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def process_file(self):
        log_event("ingestion_started", {
            "file_path": self.file_path,
            "company_id": self.company_id
        })

        try:
            file_ext = os.path.splitext(self.file_path)[1].lower()
            if file_ext == '.xlsx':
                df = pd.read_excel(self.file_path)
                log_event("file_read_success", {"type": "xlsx", "file_path": self.file_path})
            elif file_ext == '.csv':
                try:
                    df = pd.read_csv(self.file_path, encoding='utf-8')
                    log_event("file_read_success", {"type": "csv", "encoding": "utf-8", "file_path": self.file_path})
                except UnicodeDecodeError:
                    df = pd.read_csv(self.file_path, encoding='latin-1')
                    log_event("file_read_success", {"type": "csv", "encoding": "latin-1", "file_path": self.file_path})
            else:
                raise Exception(f"Unsupported file type: {file_ext}. Only .xlsx and .csv supported.")

            df.columns = [col.lower().strip() for col in df.columns]
            log_event("file_processing_started", {
                "rows_found": len(df),
                "columns_found": list(df.columns),
                "file_path": self.file_path
            })

            for index, row in df.iterrows():
                raw = row.to_dict()
                try:
                    self._process_row(raw, index + 1)
                except Exception as row_error:
                    self.error_count += 1
                    log_event("row_processing_error", {
                        "row_number": index + 1,
                        "error": str(row_error),
                        "row_data": raw
                    })
                    continue

            self.conn.commit()
            summary = {
                "file_path": self.file_path,
                "file_type": file_ext,
                "total_rows_processed": len(df),
                "ingested_count": self.ingested_count,
                "skipped_count": self.skipped_count,
                "error_count": self.error_count,
                "status": "completed"
            }
            log_event("ingestion_completed", summary)
            return summary

        except Exception as e:
            log_event("ingestion_failed", {"file_path": self.file_path, "error": str(e)})
            if self.conn:
                self.conn.rollback()
            raise

    def _process_row(self, raw_row: dict, row_number: int):
        # Fill missing optional fields with defaults
        defaults = {
            "statement_type": None,
            "category": None,
            "value_type": "Actual",
            "frequency": raw_row.get("period_type", "Monthly"),
            "currency": raw_row.get("currency", "USD")
        }
        for k, v in defaults.items():
            raw_row.setdefault(k, v)

        # Attempt mapping, fallback if None
        mapped = map_and_filter_row(raw_row)
        if mapped is None:
            mapped = {
                "line_item": raw_row.get("line_item"),
                "period_label": raw_row.get("period_label"),
                "period_type": raw_row.get("period_type", "Monthly"),
                "value_type": raw_row.get("value_type"),
                "frequency": raw_row.get("frequency"),
                "value": raw_row.get("value"),
                "currency": raw_row.get("currency"),
                "notes": f"unmapped_row:{row_number}"
            }

        # Require line_item and period_label
        if not mapped.get("line_item") or not mapped.get("period_label"):
            self.skipped_count += 1
            log_event("row_skipped", {
                "row_number": row_number,
                "reason": "Missing line_item or period_label"
            })
            return

        period_info = parse_period(mapped["period_label"], mapped.get("period_type", "Monthly"))

        with self.conn.cursor() as cur:
            # line_item_id lookup
            cur.execute("SELECT id FROM line_item_definitions WHERE name = %s", (mapped["line_item"],))
            li = cur.fetchone()
            if not li:
                self.error_count += 1
                log_event("line_item_not_found", {"row_number": row_number, "line_item": mapped["line_item"]})
                return
            line_item_id = li[0]

            # period_id lookup/insert
            cur.execute(
                "SELECT id FROM periods WHERE period_type = %s AND period_label = %s",
                (period_info["type"], period_info["label"])
            )
            pr = cur.fetchone()
            if not pr:
                cur.execute(
                    "INSERT INTO periods (period_type, period_label, start_date, end_date, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                    (period_info["type"], period_info["label"],
                     period_info["start_date"], period_info["end_date"],
                     datetime.now(), datetime.now())
                )
                period_id = cur.fetchone()[0]
            else:
                period_id = pr[0]

            # Compute stable hash
            row_hash = hash_datapoint(
                self.company_id, period_id,
                mapped["line_item"], mapped.get("value_type"),
                mapped.get("frequency"), clean_numeric_value(mapped.get("value"))
            )

            # Skip duplicates in-file
            if row_hash in self.current_file_hashes:
                self.skipped_count += 1
                log_event("duplicate_skipped", {"row_number": row_number, "hash": row_hash})
                return
            self.current_file_hashes.add(row_hash)

            # Skip duplicates in DB
            cur.execute("SELECT id FROM financial_metrics WHERE hash = %s", (row_hash,))
            if cur.fetchone():
                self.skipped_count += 1
                log_event("duplicate_skipped", {"row_number": row_number, "hash": row_hash})
                return

            # Insert metric
            cur.execute(
                """INSERT INTO financial_metrics (
                       company_id, period_id, line_item_id, value_type, frequency,
                       value, currency, source_file, source_page, source_type,
                       notes, hash, created_at, updated_at
                   ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    self.company_id, period_id, line_item_id,
                    mapped["value_type"], mapped["frequency"],
                    clean_numeric_value(mapped.get("value")), mapped["currency"],
                    os.path.basename(self.file_path),
                    int(raw_row.get("source_page", 1)),
                    "Raw", mapped.get("notes"),
                    row_hash, datetime.now(), datetime.now()
                )
            )
            self.ingested_count += 1
            log_event("metric_inserted", {
                "row_number": row_number,
                "line_item": mapped["line_item"],
                "period_label": period_info["label"],
                "value": clean_numeric_value(mapped.get("value"))
            })


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_xlsx.py <file_path> [company_id]")
        sys.exit(1)

    file_path = sys.argv[1]
    company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"Ingestion starting for file: {file_path}")
    with XLSXIngester(file_path, company_id) as ingester:
        result = ingester.process_file()
        print(f"Ingestion result: {result}")
