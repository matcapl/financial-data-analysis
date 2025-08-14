# server/scripts/ingest_xlsx.py

import pandas as pd
from datetime import datetime
import psycopg2
import sys
import os

from utils import (
    hash_datapoint,
    log_event,
    get_db_connection,
    clean_numeric_value,
    parse_period,
    get_field_synonyms,
    get_line_item_aliases,
    load_yaml_config,
    seed_line_item_definitions
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
        self.fields_config = load_yaml_config('config/fields.yaml')

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

            # Normalize headers using YAML configs
            raw_cols = [c.strip() for c in df.columns]
            synonyms = get_field_synonyms()  # Load field synonyms from fields.yaml
            aliases = get_line_item_aliases()  # Load line item aliases from fields.yaml
            canon_map = {}
            for col in raw_cols:
                lower = col.lower()
                # Check field synonyms first (e.g., period_label, value_type)
                for canon, variants in synonyms.items():
                    if lower in [v.lower() for v in variants]:
                        canon_map[col] = canon
                        break
                # Then check line item aliases (e.g., Revenue, Gross Profit)
                else:
                    canon_map[col] = aliases.get(lower, lower)
            
            # Validate required fields
            required_fields = [k for k, v in self.fields_config['fields'].items() if v.get('required', False)]
            missing = [f for f in required_fields if f not in canon_map.values()]
            if missing:
                raise ValueError(f"Missing required fields: {missing}")
            
            df = df.rename(columns=canon_map)

            # Seed line_item_definitions from YAML if needed
            seed_line_item_definitions()

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
        # Apply defaults
        defaults = {
            "statement_type": None,
            "category": None,
            "value_type": raw_row.get("value_type") or "Actual",
            "frequency": raw_row.get("frequency") or raw_row.get("period_type") or self.fields_config.get('auto_create_periods', {}).get('default_type', "Monthly"),
            "currency": raw_row.get("currency") or "USD"
        }
        for k, v in defaults.items():
            raw_row.setdefault(k, v)

        # Normalize via field_mapper
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

        # Validate required fields
        if not mapped.get("line_item") or not mapped.get("period_label"):
            raise Exception(f"Missing required fields in row {row_number}: "
                            f"line_item={mapped.get('line_item')} "
                            f"period_label={mapped.get('period_label')}")

        # Parse period using date formats from fields.yaml
        period_type = mapped.get("period_type", self.fields_config.get('auto_create_periods', {}).get('default_type', "Monthly"))
        period = parse_period(mapped["period_label"], period_type)

        # Single cursor for all DB operations
        with self.conn.cursor() as cur:
            # 1. Lookup line_item_id
            cur.execute("SELECT id FROM line_item_definitions WHERE name=%s", (mapped["line_item"],))
            li = cur.fetchone()
            print(f"DEBUG: Looking for line_item '{mapped['line_item']}', found: {li}")
            if not li:
                cur.execute("SELECT name FROM line_item_definitions")
                available = [r[0] for r in cur.fetchall()]
                raise Exception(f"Line item not found: {mapped['line_item']}. Available: {available}")
            line_item_id = li[0]

            # 2. Lookup or insert period_id
            cur.execute(
                "SELECT id FROM periods WHERE period_type=%s AND period_label=%s",
                (period["type"], period["label"])
            )
            pr = cur.fetchone()
            if pr:
                period_id = pr[0]
            else:
                if not self.fields_config.get('auto_create_periods', {}).get('enabled', False):
                    raise Exception(f"Period not found: {period['label']} and auto-creation disabled")
                cur.execute(
                    "INSERT INTO periods "
                    "(period_type,period_label,start_date,end_date,created_at,updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                    (period["type"], period["label"],
                     period["start_date"], period["end_date"],
                     datetime.now(), datetime.now())
                )
                period_id = cur.fetchone()[0]

            # 3. Compute hash
            row_hash = hash_datapoint(
                self.company_id, period_id,
                mapped["line_item"], mapped["value_type"],
                mapped["frequency"],
                clean_numeric_value(mapped["value"])
            )
            print(f"DEBUG: Computed hash for row {row_number}: {row_hash}")

            # 4. In-file duplicate check
            if row_hash in self.current_file_hashes:
                self.skipped_count += 1
                log_event("duplicate_skipped_infile", {
                    "row_number": row_number, "hash": row_hash
                })
                return

            # 5. DB duplicate check
            cur.execute("SELECT id FROM financial_metrics WHERE hash=%s", (row_hash,))
            existing = cur.fetchone()
            if existing:
                self.skipped_count += 1
                log_event("duplicate_skipped_db", {
                    "row_number": row_number,
                    "hash": row_hash,
                    "existing_id": existing[0]
                })
                return

            # 6. Insert metric
            print(f"DEBUG: About to insert metric for row {row_number}, hash={row_hash}")
            cur.execute(
                """INSERT INTO financial_metrics (
                    company_id, period_id, line_item_id, value_type, frequency,
                    value, currency, source_file, source_page, source_type,
                    notes, hash, created_at, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    self.company_id, period_id, line_item_id,
                    mapped["value_type"], mapped["frequency"],
                    clean_numeric_value(mapped["value"]), mapped["currency"],
                    os.path.basename(self.file_path),
                    int(raw_row.get("source_page", 1)),
                    "Raw", mapped.get("notes"), row_hash,
                    datetime.now(), datetime.now()
                )
            )

            # 7. Track success
            self.current_file_hashes.add(row_hash)
            self.ingested_count += 1
            log_event("metric_inserted", {
                "row_number": row_number,
                "line_item": mapped["line_item"],
                "period_label": period["label"],
                "value_type": mapped["value_type"],
                "value": clean_numeric_value(mapped["value"]),
                "hash": row_hash
            })
            print(f"DEBUG: Successfully inserted row {row_number}")

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