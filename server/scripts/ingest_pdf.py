# server/scripts/ingest_pdf.py

import fitz
import pytesseract
from pdf2image import convert_from_path
import pandas as pd
import psycopg2
import sys
import os
import re
from datetime import datetime
import pathlib

# Ensure local imports resolve
sys.path.append(str(pathlib.Path(__file__).resolve().parent))
from utils import (
    hash_datapoint, log_event, get_db_connection,
    clean_numeric_value, parse_period
)
from field_mapper import map_and_filter_row


class PDFIngester:
    def __init__(self, file_path: str, company_id: int = 1):
        """
        Enhanced PDF Ingester with fixed TableFinder handling
        and stable hashing for duplicate detection.
        """
        self.file_path = file_path
        self.company_id = company_id
        self.conn = None
        self.ingested_count = 0
        self.skipped_count = 0
        self.error_count = 0
        # Track hashes within this file
        self.current_file_hashes = set()

    def __enter__(self):
        self.conn = get_db_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def process_file(self):
        log_event("pdf_ingestion_started", {
            "file_path": self.file_path,
            "company_id": self.company_id
        })
        try:
            doc = fitz.open(self.file_path)
            for page_index in range(len(doc)):
                self._process_page(doc[page_index], page_index + 1)
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
            log_event("pdf_ingestion_failed", {
                "file_path": self.file_path,
                "error": str(e)
            })
            raise

    def _process_page(self, page, page_num):
        log_event("page_processing_started", {"page_number": page_num})
        try:
            # Fixed: handle TableFinder properly for PyMuPDF >= 1.22
            tf = page.find_tables()
            tables = []
            if tf:
                try:
                    tables = list(tf)
                except TypeError:
                    if hasattr(tf, "__len__"):
                        tables = tf
                    else:
                        tables = getattr(tf, "tables", [])

            if tables:
                log_event("tables_found", {
                    "page_number": page_num,
                    "table_count": len(tables)
                })
                for tbl_idx, tbl in enumerate(tables):
                    try:
                        df = pd.DataFrame(tbl.extract())
                        self._process_table(df, page_num, tbl_idx)
                    except Exception as tbl_err:
                        log_event("table_extraction_error", {
                            "page_number": page_num,
                            "table_index": tbl_idx,
                            "error": str(tbl_err)
                        })
            else:
                log_event("no_tables_found_using_ocr", {"page_number": page_num})
                try:
                    images = convert_from_path(
                        self.file_path, first_page=page_num, last_page=page_num
                    )
                    text = pytesseract.image_to_string(images[0])
                    self._process_text(text, page_num)
                except Exception as ocr_err:
                    log_event("ocr_extraction_error", {
                        "page_number": page_num,
                        "error": str(ocr_err)
                    })

        except Exception as e:
            self.error_count += 1
            log_event("page_processing_error", {
                "page_number": page_num,
                "error": str(e)
            })

    def _process_table(self, df, page_num, table_idx):
        """Process extracted DataFrame table rows"""
        if df.empty:
            log_event("empty_table_skipped", {
                "page_number": page_num,
                "table_index": table_idx
            })
            return

        df.columns = [str(c).strip() for c in df.columns]
        log_event("table_processing", {
            "page_number": page_num,
            "table_index": table_idx,
            "columns": df.columns.tolist(),
            "rows": len(df)
        })

        for row_idx, row in df.iterrows():
            label = str(row.iloc[0]).strip()
            if not label or label.lower() in ["nan", "none", ""]:
                continue

            for col_idx, col in enumerate(df.columns[1:], start=1):
                if col_idx >= len(row):
                    continue
                val = self._extract_number(row.iloc[col_idx])
                if val is None:
                    continue

                period_info = self._parse_period_from_header(col, page_num, table_idx)
                raw = {
                    "line_item": label,
                    "period_label": period_info["label"],
                    "period_type": period_info["type"],
                    "value_type": "Actual",
                    "frequency": period_info["type"],
                    "value": val,
                    "currency": "USD",
                    "source_file": os.path.basename(self.file_path),
                    "source_page": page_num,
                    "notes": f"Table {table_idx+1}, Row '{label}', Col '{col}'"
                }
                mapped = map_and_filter_row(raw)
                if mapped:
                    self._insert_mapped(mapped, page_num)

    def _process_text(self, text, page_num):
        """Fallback OCR text processing"""
        for idx, line in enumerate(text.split("\n"), start=1):
            ln = line.strip()
            if not ln:
                continue
            nums = self._extract_numbers_from_line(ln)
            for num in nums:
                period_info = self._infer_period_from_context(ln, page_num)
                raw = {
                    "line_item": ln,
                    "period_label": period_info["label"],
                    "period_type": period_info["type"],
                    "value_type": "Actual",
                    "frequency": period_info["type"],
                    "value": num,
                    "currency": "USD",
                    "source_file": os.path.basename(self.file_path),
                    "source_page": page_num,
                    "notes": f"Text line {idx}"
                }
                mapped = map_and_filter_row(raw)
                if mapped:
                    self._insert_mapped(mapped, page_num)

    def _insert_mapped(self, mapped_row, page_num):
        """Insert mapped row into DB with stable hash"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM line_item_definitions WHERE name = %s",
                    (mapped_row["line_item"],)
                )
                li = cur.fetchone()
                if not li:
                    self.error_count += 1
                    log_event("line_item_not_found", {"line_item": mapped_row["line_item"]})
                    return
                line_item_id = li[0]

                period_info = parse_period(
                    mapped_row["period_label"],
                    mapped_row.get("period_type", "Monthly")
                )
                cur.execute(
                    "SELECT id FROM periods WHERE period_type = %s AND period_label = %s",
                    (period_info["type"], period_info["label"])
                )
                pr = cur.fetchone()
                if pr:
                    period_id = pr[0]
                else:
                    cur.execute(
                        "INSERT INTO periods "
                        "(period_type, period_label, start_date, end_date, created_at, updated_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                        (
                            period_info["type"], period_info["label"],
                            period_info["start_date"], period_info["end_date"],
                            datetime.now(), datetime.now()
                        )
                    )
                    period_id = cur.fetchone()[0]

                try:
                    src_pg = int(mapped_row.get("source_page", page_num))
                except:
                    src_pg = page_num

                data = {
                    "company_id": self.company_id,
                    "period_id": period_id,
                    "line_item_id": line_item_id,
                    "value_type": mapped_row.get("value_type", "Actual"),
                    "frequency": mapped_row.get("frequency", period_info["type"]),
                    "value": clean_numeric_value(mapped_row["value"]),
                    "currency": mapped_row.get("currency", "USD"),
                    "source_file": mapped_row.get("source_file"),
                    "source_page": src_pg,
                    "source_type": "Raw",
                    "notes": mapped_row.get("notes", "")
                }

                # Stable hash (no timestamp)
                row_hash = hash_datapoint(
                    data["company_id"], data["period_id"],
                    mapped_row["line_item"], data["value_type"],
                    data["frequency"], data["value"]
                )

                if row_hash in self.current_file_hashes:
                    self.skipped_count += 1
                    log_event("duplicate_skipped", {"hash": row_hash})
                    return
                self.current_file_hashes.add(row_hash)

                cur.execute(
                    "SELECT 1 FROM financial_metrics WHERE hash = %s",
                    (row_hash,)
                )
                if cur.fetchone():
                    self.skipped_count += 1
                    log_event("duplicate_skipped", {"hash": row_hash})
                    return

                cur.execute(
                    """INSERT INTO financial_metrics(
                        company_id, period_id, line_item_id, value_type, frequency,
                        value, currency, source_file, source_page, source_type,
                        notes, hash, created_at, updated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        data["company_id"], data["period_id"],
                        data["line_item_id"], data["value_type"],
                        data["frequency"], data["value"], data["currency"],
                        data["source_file"], data["source_page"],
                        data["source_type"], data["notes"], row_hash,
                        datetime.now(), datetime.now()
                    )
                )
                self.ingested_count += 1
                log_event("metric_inserted", {
                    "line_item": mapped_row["line_item"],
                    "period_label": period_info["label"],
                    "value": data["value"]
                })

        except Exception as e:
            self.error_count += 1
            log_event("insert_error", {"error": str(e), "mapped_row": mapped_row})

    def _extract_number(self, cell):
        if cell is None or pd.isna(cell):
            return None
        text = str(cell).strip()
        if not text or text.lower() in ["nan", "none", "-", ""]:
            return None
        is_neg = text.startswith("(") and text.endswith(")")
        if is_neg:
            text = text[1:-1]
        cleaned = re.sub(r"[^\d\.\,\-]", "", text).replace(",", "")
        try:
            val = float(cleaned)
            return -val if is_neg else val
        except:
            return None

    def _extract_numbers_from_line(self, line):
        patterns = [r"\(\s*[\d,]+\.?\d*\s*\)", r"-?[\d,]+\.?\d*"]
        nums = []
        for p in patterns:
            for m in re.findall(p, line):
                v = self._extract_number(m)
                if v is not None:
                    nums.append(v)
        return nums

    def _parse_period_from_header(self, header, page_num, table_idx):
        hdr = str(header)
        lhdr = hdr.lower()
        if any(w in lhdr for w in ["ytd", "current"]):
            tp = "YTD"
        elif any(w in lhdr for w in ["budget", "forecast", "plan"]):
            tp = "Budget"
        elif any(w in lhdr for w in ["prior", "previous", "py"]):
            tp = "Prior Year"
        else:
            tp = "Monthly"
        lbl = f"{hdr} (Page {page_num}, Table {table_idx+1})"
        return {"type": tp, "label": lbl, "start_date": None, "end_date": None}

    def _infer_period_from_context(self, line, page_num):
        months = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
        fl = next((m for m in months if m in line.lower()), None)
        if fl:
            lbl = f"{fl.title()} {datetime.now().year}"
        else:
            lbl = f"Unknown (Page {page_num})"
        return {"type": "Monthly", "label": lbl, "start_date": None, "end_date": None}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_pdf.py <file_path> [company_id]")
        sys.exit(1)

    file_path = sys.argv[1]
    company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    with PDFIngester(file_path, company_id) as ingester:
        result = ingester.process_file()
        print(f"PDF ingestion result: {result}")
