#!/usr/bin/env python3
"""
ingest_pdf.py - Unified Three-Layer PDF Ingestion Module

This module uses the same three-layer pipeline as CSV/Excel ingestion:
1. Extraction (PDF tables or OCR text → raw rows)
2. Field Mapping (YAML-driven header and field standardization)
3. Normalization (period and value normalization)
4. Persistence (database insertion with deduplication)

Author: Financial Data Analysis Team
Version: 3.0 (Three-Layer Integration)
"""

import sys
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Union

import pandas as pd
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path

# Ensure server/scripts is on PYTHONPATH
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

from field_mapper import map_and_filter_row
from normalization import normalize_data
from persistence import persist_data
from app.utils.utils import log_event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_pdf_rows(file_path: Path) -> List[Dict[str, Any]]:
    """
    Extract raw rows from PDF:
    - Tables via PyMuPDF TableFinder
    - Fallback OCR via pytesseract
    """
    raw_rows: List[Dict[str, Any]] = []
    doc = fitz.open(str(file_path))
    for page_index in range(len(doc)):
        page = doc[page_index]
        tables = []
        try:
            tf = page.find_tables()
            tables = list(tf) if hasattr(tf, "__iter__") else tf.tables
        except Exception:
            pass

        if tables:
            log_event("pdf_tables_found", {"page": page_index + 1, "count": len(tables)})
            for tbl_idx, tbl in enumerate(tables):
                try:
                    df = pd.DataFrame(tbl.extract())
                    df.columns = [str(c).strip() for c in df.columns]
                    rows = df.to_dict(orient="records")
                    for r in rows:
                        r["_sheet_name"] = f"page_{page_index+1}_table_{tbl_idx+1}"
                        raw_rows.append(r)
                except Exception as e:
                    log_event("pdf_table_extract_error", {
                        "page": page_index + 1,
                        "table": tbl_idx + 1,
                        "error": str(e)
                    })
        else:
            log_event("pdf_no_tables", {"page": page_index + 1})
            try:
                images = convert_from_path(str(file_path),
                                           first_page=page_index+1,
                                           last_page=page_index+1)
                text = pytesseract.image_to_string(images[0])
                for line in text.splitlines():
                    if line.strip():
                        raw_rows.append({
                            "line_text": line.strip(),
                            "_sheet_name": f"page_{page_index+1}"
                        })
            except Exception as e:
                log_event("pdf_ocr_error", {"page": page_index + 1, "error": str(e)})

    doc.close()
    return raw_rows


def convert_text_rows_to_structured(raw_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert OCR text rows into structured raw data dictionaries.
    Assumes 'line_text' field in row.
    """
    structured: List[Dict[str, Any]] = []
    for row in raw_rows:
        text = row.get("line_text")
        if not text:
            continue
        parts = text.split()
        if len(parts) >= 3:
            raw = {
                "line_item": parts[0],
                "period_label": parts[1],
                "value": parts[2],
                "source_file": row.get("_sheet_name"),
                "notes": "OCR fallback"
            }
            structured.append(raw)
    return structured


def ingest_pdf(file_path: Union[str, Path], company_id: int = 1) -> Dict[str, Any]:
    """
    Main three-layer ingestion for PDF files.
    Returns summary dict with counts.
    """
    file_path = Path(file_path)
    log_event("pdf_ingestion_started", {"file_path": str(file_path), "company_id": company_id})

    # 1) Extraction
    raw_rows = extract_pdf_rows(file_path)
    if not raw_rows:
        return {
            "status": "no_data",
            "file_path": str(file_path),
            "ingested": 0,
            "skipped": 0,
            "errors": 0
        }

    # 2) Field Mapping
    mapped_rows = []
    map_errors = 0
    for idx, row in enumerate(raw_rows, start=1):
        try:
            mapped = map_and_filter_row(row)
            mapped_rows.append(mapped)
        except Exception as e:
            log_event("pdf_map_error", {"row": idx, "error": str(e)})
            map_errors += 1

    # 3) Normalization
    normalized, norm_errors = normalize_data(mapped_rows, str(file_path))

    # 4) Persistence
    # Extract company_id and period_id from first normalized row
    pid = normalized[0]["period_id"]
    cid = normalized[0]["company_id"]
    inserted = persist_data(normalized, cid, pid)

    summary = {
        "file_path": str(file_path),
        "company_id": company_id,
        "rows_extracted": len(raw_rows),
        "rows_mapped": len(mapped_rows),
        "map_errors": map_errors,
        "rows_normalized": len(normalized),
        "norm_errors": norm_errors,
        "persisted": inserted,
        "skipped": None,     # If persist_data returns only count, adjust accordingly
        "persist_errors": None,
        "status": "completed"
    }
    log_event("pdf_ingestion_completed", summary)
    return summary


def main():
    if len(sys.argv) < 2:
        print("Usage: python ingest_pdf.py <file_path> [company_id]")
        sys.exit(1)

    file_path = sys.argv[1]
    company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    result = ingest_pdf(file_path, company_id)
    print(f"Ingestion summary: {result}")


if __name__ == "__main__":
    main()
