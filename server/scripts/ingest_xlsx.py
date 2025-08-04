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
            ext = os.path.splitext(self.file_path)[1].lower()
            if ext == ".xlsx":
                df = pd.read_excel(self.file_path)
                log_event("file_read_success", {"type": "xlsx", "file_path": self.file_path})
            elif ext == ".csv":
                try:
                    df = pd.read_csv(self.file_path, encoding="utf-8")
                    log_event("file_read_success", {"type": "csv-utf8", "file_path": self.file_path})
                except UnicodeDecodeError:
                    df = pd.read_csv(self.file_path, encoding="latin-1")
                    log_event("file_read_success", {"type": "csv-latin1", "file_path": self.file_path})
            else:
                raise Exception(f"Unsupported file type: {ext}")

            # Normalize headers: map variants to canonical names
            raw_cols = [c.strip() for c in df.columns]
            synonyms = {
                "company_id":      ["company_id","companyid","company","co_id"],
                "company_name":    ["company_name","companyname","company","co_name","name"],
                "line_item":       ["line_item","lineitem","item","metric","line item","financial_item"],
                "period_label":    ["period_label","periodlabel","period","date","fiscal_period"],
                "period_type":     ["period_type","periodtype","frequency","freq","type"],
                "value":           ["value","amount","val","figure"],
                "value_type":      ["value_type","valuetype","type","actual","budget","prior"],
                "frequency":       ["frequency","freq","period_type","periodtype"],
                "currency":        ["currency","curr","ccy"],
                "source_file":     ["source_file","file","filename","source"],
                "source_page":     ["source_page","page","pageno","page_number"],
                "notes":           ["notes","note","comments","description"]
            }
            canon_map = {}
            for col in raw_cols:
                lower = col.lower()
                for canon, variants in synonyms.items():
                    if lower in variants:
                        canon_map[col] = canon
                        break
                else:
                    canon_map[col] = lower
            df = df.rename(columns=canon_map)

            log_event("file_processing_started", {
                "rows_found": len(df),
                "columns_found": list(df.columns),
                "file_path": self.file_path
            })

            for idx, row in df.iterrows():
                raw = row.to_dict()
                try:
                    self._process_row(raw, idx + 1)
                except Exception as e:
                    self.error_count += 1
                    log_event("row_processing_error", {
                        "row_number": idx + 1,
                        "error": str(e),
                        "row_data": raw
                    })

            self.conn.commit()
            summary = {
                "file_path": self.file_path,
                "file_type": ext,
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
        # Defaults and ensure canonical keys exist
        defaults = {
            "statement_type": None,
            "category": None,
            "value_type": raw_row.get("value_type") or "Actual",
            "frequency": raw_row.get("frequency") or raw_row.get("period_type") or "Monthly",
            "currency": raw_row.get("currency") or "USD"
        }
        for k, v in defaults.items():
            raw_row.setdefault(k, v)

        # Normalize via field_mapper, fallback if None
        mapped = map_and_filter_row(raw_row) or {
            "line_item": raw_row.get("line_item"),
            "period_label": raw_row.get("period_label"),
            "period_type": raw_row.get("period_type"),
            "value_type": raw_row.get("value_type"),
            "frequency": raw_row.get("frequency"),
            "value": raw_row.get("value"),
            "currency": raw_row.get("currency"),
            "notes": f"unmapped_row:{row_number}"
        }

        # Debug
        print("DEBUG: ROW NUM", row_number, "RAW", raw_row)
        print("DEBUG: MAPPED", mapped)

        # Required fields
        if not mapped.get("line_item") or not mapped.get("period_label"):
            raise Exception(f"Missing required fields in row {row_number}: "
                            f"line_item={mapped.get('line_item')} period_label={mapped.get('period_label')}")

        # Parse period
        period = parse_period(mapped["period_label"], mapped.get("period_type", "Monthly"))

        with self.conn.cursor() as cur:
            # line_item_id lookup
            cur.execute("SELECT id FROM line_item_definitions WHERE name=%s", (mapped["line_item"],))
            li = cur.fetchone()
            print(f"DEBUG: Looking for line_item '{mapped['line_item']}', found: {li}")
            if not li:
                print("DEBUG: Available line items in DB:")
                cur.execute("SELECT name FROM line_item_definitions")
                print([row[0] for row in cur.fetchall()])
                raise Exception(f"Line item not found in definitions: {mapped['line_item']}")
            line_item_id = li[0]

            # period_id lookup/insert
            cur.execute(
                "SELECT id FROM periods WHERE period_type=%s AND period_label=%s",
                (period["type"], period["label"])
            )
            pr = cur.fetchone()
            if pr:
                period_id = pr[0]
            else:
                cur.execute(
                    "INSERT INTO periods (period_type,period_label,start_date,end_date,created_at,updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                    (period["type"], period["label"], period["start_date"], period["end_date"],
                     datetime.now(), datetime.now())
                )
                period_id = cur.fetchone()[0]

            # Compute hash (includes value_type)
            row_hash = hash_datapoint(
                self.company_id, period_id, mapped["line_item"],
                mapped["value_type"], mapped["frequency"],
                clean_numeric_value(mapped["value"])
            )

            # Skip in-file duplicates
            if row_hash in self.current_file_hashes:
                self.skipped_count += 1
                log_event("duplicate_skipped", {"row_number": row_number, "hash": row_hash})
                return
            self.current_file_hashes.add(row_hash)

            # Skip existing in DB
            cur.execute("SELECT id FROM financial_metrics WHERE hash=%s", (row_hash,))
            if cur.fetchone():
                self.skipped_count += 1
                log_event("duplicate_skipped", {"row_number": row_number, "hash": row_hash})
                return

        # Insert metric
        print(f"DEBUG: About to insert metric for row {row_number}, hash={row_hash}")
        cur.execute(
            """INSERT INTO financial_metrics (
            company_id, period_id, line_item_id, value_type, frequency,
            value, currency, source_file, source_page, source_type,
            notes, hash, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    self.company_id, period_id, line_item_id,
                    mapped["value_type"], mapped["frequency"],
                    clean_numeric_value(mapped["value"]), mapped["currency"],
                    os.path.basename(self.file_path), int(raw_row.get("source_page", 1)),
                    "Raw", mapped.get("notes"), row_hash,
                    datetime.now(), datetime.now()
                )
        )
        self.ingested_count += 1
        log_event("metric_inserted", {
            "row_number": row_number,
            "line_item": mapped["line_item"],
            "period_label": period["label"],
            "value_type": mapped["value_type"],
            "value": clean_numeric_value(mapped["value"])
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
