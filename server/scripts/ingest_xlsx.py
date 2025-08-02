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
        # Track hashes within this file only
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
                try:
                    df = pd.read_excel(self.file_path)
                    log_event("file_read_success", {"type": "xlsx", "file_path": self.file_path})
                except Exception as e:
                    log_event("file_read_error", {"type": "xlsx", "error": str(e), "file_path": self.file_path})
                    raise
            elif file_ext == '.csv':
                try:
                    df = pd.read_csv(self.file_path, encoding='utf-8')
                    log_event("file_read_success", {"type": "csv", "encoding": "utf-8", "file_path": self.file_path})
                except UnicodeDecodeError:
                    df = pd.read_csv(self.file_path, encoding='latin-1')
                    log_event("file_read_success", {"type": "csv", "encoding": "latin-1", "file_path": self.file_path})
                except Exception as e:
                    df = pd.read_csv(self.file_path, encoding='cp1252')
                    log_event("file_read_success", {"type": "csv", "encoding": "cp1252", "file_path": self.file_path})
            else:
                raise Exception(f"Unsupported file type: {file_ext}. Only .xlsx and .csv files are supported.")

            df.columns = [col.lower().strip() for col in df.columns]
            log_event("file_processing_started", {
                "rows_found": len(df),
                "columns_found": list(df.columns),
                "file_path": self.file_path
            })

            for index, row in df.iterrows():
                raw = row.to_dict()
                mapped = map_and_filter_row(raw)
                if mapped is None:
                    continue
                try:
                    self._process_row(mapped, index + 1)
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

    def _process_row(self, row, row_number):
        if pd.isna(row.get("line_item")) or pd.isna(row.get("period_label")):
            self.skipped_count += 1
            log_event("row_skipped", {
                "row_number": row_number,
                "reason": "Missing line_item or period_label"
            })
            return

        line_item = str(row["line_item"]).strip()
        valid_items = ["Revenue", "Gross Profit", "EBITDA"]
        if line_item not in valid_items:
            self.skipped_count += 1
            log_event("row_skipped", {
                "row_number": row_number,
                "reason": f"Invalid line_item: {line_item}. Valid items: {valid_items}"
            })
            return

        period_info = parse_period(row["period_label"], row.get("period_type", "Monthly"))

        with self.conn.cursor() as cur:
            # Lookup or insert line_item_id
            cur.execute("SELECT id FROM line_item_definitions WHERE name = %s", (line_item,))
            li = cur.fetchone()
            if not li:
                self.error_count += 1
                log_event("line_item_not_found", {"row_number": row_number, "line_item": line_item})
                return
            line_item_id = li[0]

            # Lookup or insert period_id
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

            # Coerce source_page
            raw_page = row.get("source_page")
            try:
                source_page = int(raw_page)
            except (TypeError, ValueError):
                source_page = 1

            # Build data dict
            data = {
                "company_id": self.company_id,
                "period_id": period_id,
                "line_item_id": line_item_id,
                "value_type": row.get("value_type", "Actual"),
                "frequency": row.get("frequency", period_info["type"]),
                "value": clean_numeric_value(row.get("value")),
                "currency": row.get("currency", "USD"),
                "source_file": os.path.basename(self.file_path),
                "source_page": source_page,
                "source_type": "Raw",
                "notes": row.get("notes", "")
            }

            # Compute stable hash (omit timestamp)
            row_hash = hash_datapoint(
                data["company_id"], data["period_id"],
                line_item, data["value_type"], data["frequency"], data["value"]
            )

            # Skip duplicates within this file
            if row_hash in self.current_file_hashes:
                self.skipped_count += 1
                log_event("duplicate_skipped", {
                    "row_number": row_number,
                    "hash": row_hash
                })
                return
            self.current_file_hashes.add(row_hash)

            # Skip existing in DB
            cur.execute("SELECT id FROM financial_metrics WHERE hash = %s", (row_hash,))
            if cur.fetchone():
                self.skipped_count += 1
                log_event("duplicate_skipped", {
                    "row_number": row_number,
                    "hash": row_hash
                })
                return

            # Insert metric
            cur.execute(
                """INSERT INTO financial_metrics (
                    company_id, period_id, line_item_id, value_type, frequency,
                    value, currency, source_file, source_page, source_type,
                    notes, hash, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    data["company_id"], data["period_id"], data["line_item_id"],
                    data["value_type"], data["frequency"], data["value"],
                    data["currency"], data["source_file"], data["source_page"],
                    data["source_type"], data["notes"], row_hash,
                    datetime.now(), datetime.now()
                )
            )
            self.ingested_count += 1
            log_event("metric_inserted", {
                "row_number": row_number,
                "line_item": line_item,
                "period_label": period_info["label"],
                "value": data["value"]
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
