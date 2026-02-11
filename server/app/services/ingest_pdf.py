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
import re
from pathlib import Path
from typing import List, Dict, Any, Union, Optional

import pandas as pd
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
import shutil
import subprocess
import tempfile

# Uses canonical services modules on PYTHONPATH
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

from field_mapper import map_and_filter_row
from normalization import normalize_data, normalize_period_label
from persistence import persist_data
from raw_persistence import persist_raw_facts
from quality_gate import assess_revenue_analyst_quality_from_db
from validator import validate_company_monthly_series
from app.utils.utils import log_event, get_db_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _period_hint_from_filename(filename: str) -> str | None:
    """Best-effort monthly period label (YYYY-MM) derived from filename."""
    if not filename:
        return None

    # Normalize separators so month tokens match even when filename uses underscores.
    name = filename.lower().replace('_', ' ').replace('-', ' ')
    month_map = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }

    # Common patterns: "Feb25", "Feb-25", "February 2025"
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s_\-]*('?)(\d{2,4})\b", name)
    if not m:
        return None

    month = month_map.get(m.group(1)[:3])
    year = int(m.group(3))
    if year < 100:
        year += 2000

    if not month:
        return None

    return f"{year}-{month:02d}"


def _has_monthly_revenue_candidate(rows: List[Dict[str, Any]]) -> bool:
    """Return True if extracted rows already contain monthly Revenue candidates."""
    for r in rows or []:
        try:
            li = str(r.get('line_item') or '').strip().lower()
            pl = str(r.get('period_label') or '').strip()
            if li == 'revenue' and len(pl) == 7 and pl[4] == '-' and pl[:4].isdigit():
                return True
        except Exception:
            continue
    return False


def _supplement_monthly_series_via_pdftotext(file_path: Path) -> List[Dict[str, Any]]:
    """Best-effort extraction of month-column tables via `pdftotext -layout`.

    This is a general fallback when PyMuPDF table extraction fails to surface
    month-column matrices (common in board packs).

    Returns raw rows compatible with mapping/normalization.
    """

    if shutil.which('pdftotext') is None:
        return []

    import subprocess

    # Extract text to a temp file
    out_fd, out_path = tempfile.mkstemp(prefix='pdftotext_', suffix='.txt')
    os.close(out_fd)

    try:
        subprocess.run(
            ['pdftotext', '-layout', str(file_path), out_path],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        text = Path(out_path).read_text(errors='ignore')
    except Exception:
        return []
    finally:
        try:
            Path(out_path).unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass

    month_map = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'}

    def parse_months_line(line: str) -> List[str]:
        months = []
        for mon, yy in re.findall(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(\d{2})\b', line):
            months.append(f"20{yy}-{month_map[mon]}")
        return months

    def parse_money(tok: str) -> Optional[str]:
        t = tok.strip()
        if not t:
            return None
        # Keep original text; normalization will parse into numeric.
        if not re.fullmatch(r"[\d,().\-]+", t):
            return None
        return t

    lines = text.splitlines()

    # Heuristic: find a header line with many month tokens and a nearby "Revenue" row with many numbers.
    best_rows: List[Dict[str, Any]] = []
    for i, line in enumerate(lines):
        months = parse_months_line(line)
        if len(months) < 6:
            continue

        # search next ~40 lines for a Revenue row
        for j in range(i + 1, min(i + 40, len(lines))):
            l = lines[j]
            if not re.match(r'^\s*Revenue\b', l):
                continue

            # extract number-like tokens after the label
            rest = l.strip()[len('Revenue'):].strip()
            toks = re.split(r'\s+', rest)
            vals = [parse_money(t) for t in toks]
            vals = [v for v in vals if v is not None]
            if len(vals) < 6:
                continue

            # map first N values to first N months
            n = min(len(months), len(vals))
            rows = []
            for idx in range(n):
                rows.append({
                    'line_item': 'Revenue',
                    'period_label': months[idx],
                    'period_type': 'Monthly',
                    'period_scope': 'Period',
                    'value_type': 'Actual',
                    'value': vals[idx],
                    'currency': 'GBP',
                    'source_file': f"{file_path.name}#pdftotext",
                    'source_type': 'pdf',
                    'notes': 'PDF: pdftotext month-matrix fallback',
                    'extraction_method': 'pdftotext',
                    'confidence': 0.75,
                })

            # Prefer the densest candidate
            if len(rows) > len(best_rows):
                best_rows = rows

    return best_rows


def _ocr_to_searchable_pdf(input_pdf: Path, *, max_pages: Optional[int] = None) -> Optional[Path]:
    """Run OCR (locally) and return a searchable PDF path.

    Uses `python -m ocrmypdf` when available. Returns None if OCR can't run.
    """
    if not input_pdf.exists():
        return None

    if shutil.which("tesseract") is None:
        log_event("pdf_ocr_unavailable", {"reason": "tesseract_not_found"})
        return None

    try:
        import importlib.util

        if importlib.util.find_spec("ocrmypdf") is None:
            log_event("pdf_ocr_unavailable", {"reason": "ocrmypdf_not_installed"})
            return None
    except Exception:
        return None

    out_fd, out_path = tempfile.mkstemp(prefix="ocr_", suffix=".pdf")
    os.close(out_fd)
    out_pdf = Path(out_path)

    # ocrmypdf doesn't offer a perfect "max pages" flag; keep hook for future.
    cmd = [
        sys.executable,
        "-m",
        "ocrmypdf",
        "--skip-text",  # only OCR pages without text
        "--quiet",
        str(input_pdf),
        str(out_pdf),
    ]

    try:
        log_event("pdf_ocr_started", {"input": str(input_pdf), "output": str(out_pdf), "cmd": cmd})
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_event("pdf_ocr_completed", {"output": str(out_pdf)})
        return out_pdf
    except Exception as e:
        log_event("pdf_ocr_failed", {"error": str(e)})
        try:
            out_pdf.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def _detect_units_label(page_text: str) -> str:
    """Detect common board-pack units/scale markers from page text."""

    import re

    if not page_text:
        return ''

    t = page_text.lower()

    # Common conventions: ( £000 ), £000, £'000, (000), £m
    if re.search(r"£\s*[’']?\s*000|\(\s*£\s*[’']?\s*000\s*\)|\b000s\b|\bthousand\b|\b\(000\)\b|\b\(k\)\b|\b£k\b", t):
        return '£000'

    if re.search(r"£\s*m\b|\b\(m\)\b|\bmillion\b|\b£m\b", t):
        return '£m'

    return ''


def extract_pdf_rows(file_path: Path) -> List[Dict[str, Any]]:
    """
    Extract raw rows from PDF with enhanced parsing:
    - Enhanced table extraction with merged cell handling
    - Multi-line cell parsing for financial data
    - Text-based fallback with pattern recognition

    Also propagates page-level unit hints (e.g. £000 / £m) into row notes so
    downstream normalisation can scale values consistently.
    """
    raw_rows: List[Dict[str, Any]] = []
    doc = fitz.open(str(file_path))

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_rows = []

        try:
            page_text = page.get_text("text")
        except Exception:
            page_text = ''

        units_label = _detect_units_label(page_text)
        ytd_hint = 'ytd' in (page_text or '').lower() or 'year to date' in (page_text or '').lower()

        # Try enhanced table extraction first
        page_rows.extend(_extract_enhanced_tables(page, page_index))

        # If table extraction is sparse, augment with text-based extraction
        if len(page_rows) < 20:
            page_rows.extend(_extract_text_based_data(page, file_path, page_index))

        # Ensure context_key / period_scope is always present (at least page-level)
        for r in page_rows:
            if not r.get('context_key'):
                r['context_key'] = f"p{page_index+1}_t{r.get('source_table') or 0}_generic"

            if units_label:
                existing = str(r.get('notes') or '')
                if 'units=' not in existing:
                    r['notes'] = (existing + f" [units={units_label}]").strip()

            ck = str(r.get('context_key') or '')
            nt = str(r.get('notes') or '')
            current_scope = str(r.get('period_scope') or '').strip() or None

            # If the page clearly advertises YTD and this looks like a P&L table section,
            # treat the facts as YTD-scoped (upgrade Period -> YTD).
            if ytd_hint and ('_pl' in ck.lower() or ck.lower().endswith('pl')):
                r['period_scope'] = 'YTD'
                if 'ytd' not in ck.lower():
                    r['context_key'] = (ck + '_ytd') if ck else 'ytd'
                existing = str(r.get('notes') or '')
                if 'ytd' not in existing.lower():
                    r['notes'] = (existing + ' [ytd]').strip()
            elif not current_scope:
                r['period_scope'] = 'YTD' if 'ytd' in (ck + ' ' + nt).lower() else 'Period'

        raw_rows.extend(page_rows)

    doc.close()
    return raw_rows


def _extract_enhanced_tables(page, page_index: int) -> List[Dict[str, Any]]:
    """Enhanced table extraction that handles merged cells and complex structures"""
    rows = []
    
    try:
        tf = page.find_tables()
        tables = list(tf) if hasattr(tf, "__iter__") else tf.tables
        
        if tables:
            log_event("pdf_tables_found", {"page": page_index + 1, "count": len(tables)})
            
            for tbl_idx, tbl in enumerate(tables):
                try:
                    # Get raw table data
                    table_data = tbl.extract()
                    
                    # Enhanced processing for complex tables
                    processed_rows = _process_complex_table(table_data, page_index, tbl_idx)
                    rows.extend(processed_rows)
                    
                except Exception as e:
                    log_event("pdf_table_extract_error", {
                        "page": page_index + 1,
                        "table": tbl_idx + 1,
                        "error": str(e)
                    })
    except Exception as e:
        log_event("pdf_table_find_error", {"page": page_index + 1, "error": str(e)})
    
    return rows




def _detect_context_key(table_data: List[List], page_index: int, tbl_idx: int) -> str:
    """Derive a semantic context key for a table.

    Robustness goal: detect YTD/run-rate/etc even when the first cell is blank.
    """

    header = ''
    try:
        pieces = []
        for r in (table_data or [])[:3]:
            for c in (r or [])[:4]:
                if c is None:
                    continue
                s = str(c).strip()
                if s:
                    pieces.append(s)
        header = ' '.join(pieces)
    except Exception:
        header = ''

    h = header.lower()

    # Semantic context tags to prevent coordinate collisions across sections
    tag = 'table'
    if 'profit and loss' in h or 'p&l' in h or 'profit & loss' in h:
        tag = 'pl_ytd' if 'ytd' in h else 'pl'
    elif 'regional dashboard' in h:
        tag = 'regional_dashboard'
    elif 'site dashboard' in h or 'site performance' in h:
        tag = 'site_dashboard'
    elif 'executive summary' in h or 'key highlights' in h:
        tag = 'exec_summary'
    elif 'kpi' in h or 'dashboard' in h:
        tag = 'kpi'
    elif 'run-rate' in h or 'run rate' in h:
        tag = 'run_rate'
    elif 'site' in h or 'club' in h or 'location' in h:
        tag = 'site'

    # Include page/table plus semantic tag. Preserve YTD signal across any section.
    if 'ytd' in h and 'ytd' not in tag:
        tag = f"{tag}_ytd"

    return f"p{page_index+1}_t{tbl_idx+1}_{tag}"


def _coerce_cell_text(cell: Any) -> str:
    if cell is None:
        return ''
    try:
        return str(cell).strip()
    except Exception:
        return ''


def _looks_numeric_cell(text: str) -> bool:
    import re
    if not text:
        return False
    return bool(re.search(r"[0-9]", text)) and bool(re.search(r"[0-9,().-]", text))


def _extract_header_mapped_table(table_data: List[List], page_index: int, tbl_idx: int) -> List[Dict[str, Any]]:
    """Extract facts from a typical matrix table: line items in col 0, values in other cols.

    Determines period/scenario from column headers and emits rows with proper period_label/value_type.
    """
    if not table_data or len(table_data) < 2:
        return []

    # Find a plausible header row block by scanning the first few rows
    scan_limit = min(8, len(table_data))
    header_rows = []
    for i in range(scan_limit):
        row_text = " ".join(_coerce_cell_text(c) for c in table_data[i] if _coerce_cell_text(c))
        if not row_text:
            continue
        # Heuristic: header rows mention periods or scenarios
        if any(k in row_text.lower() for k in ["ytd", "q", "fy", "cy", "budget", "actual", "prior", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
            header_rows.append(table_data[i])
        if len(header_rows) >= 2:
            break
    if not header_rows:
        header_rows = table_data[:1]
    col_count = max(len(r) for r in header_rows)

    col_meta: List[Dict[str, Any]] = []
    for col_idx in range(col_count):
        pieces = []
        for r in header_rows:
            if col_idx < len(r):
                t = _coerce_cell_text(r[col_idx])
                if t:
                    pieces.append(t)
        header_text = ' '.join(pieces)
        header_low = header_text.lower()

        scenario = None
        if 'budget' in header_low or 'plan' in header_low:
            scenario = 'Budget'
        elif 'prior' in header_low or 'py' in header_low:
            scenario = 'Prior Year'
        elif 'forecast' in header_low or 'fcst' in header_low:
            scenario = 'Forecast'
        elif 'actual' in header_low:
            scenario = 'Actual'
        elif 'ytd' in header_low:
            scenario = scenario or 'Actual'

        period_label = None
        period_type = None
        # Try to normalize any period-like substring from the header
        # Use the entire header text; normalization will attempt aliases/patterns.
        canon = normalize_period_label(header_text)
        if canon and canon[0]:
            period_label, period_type = canon

        col_meta.append({
            'col_idx': col_idx,
            'header_text': header_text,
            'scenario': scenario,
            'period_label': period_label,
            'period_type': period_type,
        })

    # Find data rows (skip rows we used as headers, but keep simple)
    header_row_count = len(header_rows)
    context_key = _detect_context_key(table_data, page_index, tbl_idx)

    rows: List[Dict[str, Any]] = []
    for row_idx, row in enumerate(table_data[header_row_count:], start=header_row_count):
        if not row or len(row) < 2:
            continue
        line_item = _coerce_cell_text(row[0])
        if not line_item:
            continue

        for col_idx in range(1, min(len(row), len(col_meta))):
            meta = col_meta[col_idx]
            cell_text = _coerce_cell_text(row[col_idx])
            if not _looks_numeric_cell(cell_text):
                continue

            if not meta.get('period_label'):
                continue

            rows.append({
                'context_key': context_key,
                'line_item': _clean_line_item_name(line_item),
                'value': cell_text,
                'period_label': meta.get('period_label'),
                'period_type': meta.get('period_type') or 'Monthly',
                'period_scope': 'YTD' if ('ytd' in (meta.get('header_text') or '').lower() or 'ytd' in (context_key or '').lower()) else 'Period',
                'value_type': meta.get('scenario') or 'Actual',
                'frequency': meta.get('period_type') or 'Monthly',
                'currency': 'GBP',
                'source_file': f"page_{page_index+1}_table_{tbl_idx+1}",
                'source_page': page_index + 1,
                'source_table': tbl_idx + 1,
                'source_row': row_idx,
                'source_col': meta.get('header_text') or f"col_{col_idx}",
                'notes': 'PDF: header-mapped table',
                'extraction_method': 'pymupdf_table',
                'confidence': 0.6,
            })

    return rows

def _process_complex_table(table_data: List[List], page_index: int, tbl_idx: int) -> List[Dict[str, Any]]:
    """Process complex tables with merged cells and financial data structures"""
    rows = []

    # First, try the dedicated board-pack P&L extractor (high signal)
    pl_rows = _extract_board_pack_pl_table(table_data, page_index, tbl_idx)
    if pl_rows:
        return pl_rows

    # Next, try month-matrix tables (months across columns; KPIs down rows).
    # This is a common board-pack pattern and is more robust than prose parsing.
    month_rows = _extract_month_matrix_table(table_data, page_index, tbl_idx)
    if month_rows:
        return month_rows

    # Next, try a generic header-mapped table extractor (period/scenario from headers)
    generic_rows = _extract_header_mapped_table(table_data, page_index, tbl_idx)
    if generic_rows:
        return generic_rows
    
    if not table_data:
        return rows
    
    # Use a simpler approach: look for the specific row with financial data
    for row_idx, row in enumerate(table_data):
        if not row:
            continue
            
        # Look for cells with financial line items and corresponding values
        for col_idx, cell in enumerate(row):
            if (cell and isinstance(cell, str) and len(cell.strip()) > 50 and
                '\n' in cell and any(term in cell.lower() for term in ['revenue', 'profit', 'cost', 'staff'])):
                
                # Found financial data - parse it
                lines = cell.split('\n')
                
                # Look for corresponding values in other columns
                for val_col_idx, val_cell in enumerate(row):
                    if val_col_idx != col_idx and val_cell and '\n' in str(val_cell):
                        values = str(val_cell).split('\n')
                        
                        # Match line items with values
                        for i, line_item in enumerate(lines):
                            line_item = line_item.strip()
                            if (line_item and i < len(values) and 
                                _is_financial_line_item(line_item) and values[i].strip()):
                                
                                value = values[i].strip()
                                # Extract first number from value if it contains multiple
                                import re
                                numbers = re.findall(r'[\d,().-]+', value)
                                if numbers:
                                    clean_value = numbers[0]
                                    
                                    context_key = _detect_context_key(table_data, page_index, tbl_idx)
                                    metric = {
                                        "context_key": context_key,
                                        "line_item": _clean_line_item_name(line_item),
                                        "value": clean_value,
                                        "period_label": None,
                                        "period_type": "Monthly",
                                        "period_scope": "YTD" if 'ytd' in context_key.lower() else "Period",
                                        "value_type": "Actual",
                                        "frequency": "Monthly", 
                                        "currency": "GBP",
                                        "source_file": f"page_{page_index+1}_table_{tbl_idx+1}",
                                        "source_page": page_index + 1,
                                        "source_table": tbl_idx + 1,
                                        "source_row": row_idx,
                                        "source_col": f"col_{val_col_idx}",
                                        "notes": f"PDF: {line_item[:30]}",
                                        "_sheet_name": f"page_{page_index+1}_table_{tbl_idx+1}",
                                        "_source_row": row_idx,
                                        "extraction_method": "pymupdf_table_simple",
                                        "confidence": 0.35,
                                    }
                                    rows.append(metric)
    
    return rows




def _extract_board_pack_pl_table(table_data: List[List], page_index: int, tbl_idx: int) -> List[Dict[str, Any]]:
    """Extract the main board-pack P&L table structure produced by PyMuPDF.

    The sample pack renders as a 5-column table where:
    - Column 0 contains many line items separated by newlines
    - Column 2 contains the Actual column values (often split across multiple table rows)
    - Column 3 contains four values per line (Budget, Prior Year, Var to Budget, Var to Prior)

    Returns metrics in the same row format expected by field_mapper/normalization.
    """
    import re

    if not table_data or len(table_data) < 3:
        return []

    # Find the row that contains the long line-item list (usually includes 'Revenue' etc.)
    line_item_cell = None
    for row in table_data:
        c0 = row[0] if len(row) > 0 else None
        if isinstance(c0, str) and "\n" in c0 and 'Revenue' in c0 and 'PROFIT AND LOSS' not in c0:
            line_item_cell = c0
            break

    if not line_item_cell:
        return []

    line_items = [ln.strip() for ln in line_item_cell.split("\n") if ln.strip()]

    # Actual values: concatenate all strings found in column 2
    actual_values: list[str] = []
    for row in table_data:
        c2 = row[2] if len(row) > 2 else None
        if isinstance(c2, str) and c2.strip():
            actual_values.extend([ln.strip() for ln in c2.split("\n") if ln.strip()])

    # Bundle values: concatenate all lines in column 3
    bundle_lines: list[str] = []
    for row in table_data:
        c3 = row[3] if len(row) > 3 else None
        if isinstance(c3, str) and c3.strip():
            bundle_lines.extend([ln.strip() for ln in c3.split("\n") if ln.strip()])

    # Heuristic sanity: we need meaningful counts
    if len(actual_values) < 5 or len(bundle_lines) < 5:
        return []

    # Attempt to detect reporting month/year from the table header (row 0)
    header_text = str(table_data[0][0]) if table_data and table_data[0] and table_data[0][0] else ''
    period_label = None
    m = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', header_text, re.IGNORECASE)
    if m:
        month_map = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        }
        month = month_map[m.group(1).lower()]
        year = int(m.group(2))
        period_label = f"{year}-{month:02d}"

    currency = 'GBP' if '£' in header_text else None

    def split_bundle(line: str) -> list[str]:
        # Split by whitespace into up to 4 columns (budget/prior/var/var)
        parts = [p for p in line.replace(' ', ' ').split(' ') if p]
        return parts

    metrics: List[Dict[str, Any]] = []
    n = min(len(line_items), len(actual_values), len(bundle_lines))

    for i in range(n):
        li = line_items[i]
        act = actual_values[i]
        bundle = split_bundle(bundle_lines[i])
        if not bundle:
            continue

        base = {
            'line_item': _clean_line_item_name(li),
            'period_label': period_label,
            'period_type': 'Monthly',
            'period_scope': 'YTD' if 'ytd' in header_text.lower() else 'Period',
            'frequency': 'Monthly',
            'source_file': f"page_{page_index+1}_table_{tbl_idx+1}",
            'source_page': page_index + 1,
            'source_table': tbl_idx + 1,
            'source_row': i,
            'notes': 'PDF: Board pack P&L',
            '_sheet_name': f"page_{page_index+1}_table_{tbl_idx+1}",
            '_source_row': i,
            'extraction_method': 'pymupdf_table',
            'confidence': 0.7,
        }
        if currency:
            base['currency'] = currency

        # Actual
        metrics.append({**base, 'value_type': 'Actual', 'value': act, 'source_col': 'Actual'})

        # Budget/Prior/Variances (if present)
        if len(bundle) >= 1:
            metrics.append({**base, 'value_type': 'Budget', 'value': bundle[0], 'source_col': 'Budget'})
        if len(bundle) >= 2:
            metrics.append({**base, 'value_type': 'Prior Year', 'value': bundle[1], 'source_col': 'Prior Year'})
        if len(bundle) >= 3:
            metrics.append({**base, 'value_type': 'Variance to budget', 'value': bundle[2], 'source_col': 'Variance to budget'})
        if len(bundle) >= 4:
            metrics.append({**base, 'value_type': 'Variance to prior year', 'value': bundle[3], 'source_col': 'Variance to prior year'})

    return metrics


def _extract_month_matrix_table(table_data: List[List], page_index: int, tbl_idx: int) -> List[Dict[str, Any]]:
    """Extract month-column matrix tables into one fact per (row, month).

    This targets common board-pack layouts where:
    - A header row includes month labels across columns (e.g. "Jan 25", "2025-10", "Oct-25")
    - The first column is a line item label (e.g. Revenue, Closing Cash)
    - Remaining columns contain values.

    The goal is robustness across packs, not perfect template matching.
    If we can't confidently identify month columns + numeric cells, return [].
    """

    import re

    if not table_data or len(table_data) < 2:
        return []

    month_map = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }

    def norm_cell(x: Any) -> str:
        if x is None:
            return ''
        return str(x).replace('\u00a0', ' ').strip()

    def parse_month_token(s: str) -> Optional[str]:
        """Return YYYY-MM if a month token is detected, else None."""
        if not s:
            return None

        t = s.strip()

        # Patterns: "Jan 25", "Mar25", "Oct-25", "Oct 2025"
        m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-_/]*('?)((?:\d{2})|(?:20\d{2}))\b", t, re.IGNORECASE)
        if m:
            mon = month_map.get(m.group(1).lower()[:3])
            year = int(m.group(3))
            if year < 100:
                year += 2000
            if mon:
                return f"{year}-{mon:02d}"

        # Pattern: YYYY-MM (or YYYY/M)
        m = re.search(r"\b(20\d{2})[\-/](\d{1,2})\b", t)
        if m:
            year = int(m.group(1))
            month = int(m.group(2))
            if 1 <= month <= 12:
                return f"{year}-{month:02d}"

        return None

    def looks_numeric(s: str) -> bool:
        if not s:
            return False
        # common financial number patterns: 1,234 ; (123) ; -123 ; 12.3
        return bool(re.search(r"\d", s)) and bool(re.fullmatch(r"[\s£$€()\-+.,\d%]+", s))

    def scenario_from_header(s: str) -> Optional[str]:
        t = (s or '').strip().lower()
        if not t:
            return None
        if 'budget' in t:
            return 'Budget'
        if 'prior' in t or 'py' in t or 'last year' in t:
            return 'Prior Year'
        if 'forecast' in t or 'fcst' in t or 'outturn' in t or 'run rate' in t:
            return 'Forecast'
        if 'variance' in t or 'vs' in t:
            return 'Variance'
        if 'actual' in t:
            return 'Actual'
        return None

    # Identify the best header row: highest count of month tokens.
    header_row_idx = None
    header_months: Dict[int, str] = {}

    for r_idx in range(min(8, len(table_data))):
        row = table_data[r_idx] or []
        months = {}
        for c_idx, cell in enumerate(row):
            m = parse_month_token(norm_cell(cell))
            if m:
                months[c_idx] = m
        if len(months) >= 3 and (header_row_idx is None or len(months) > len(header_months)):
            header_row_idx = r_idx
            header_months = months

    if header_row_idx is None:
        return []

    # Optional scenario row immediately below the month header row
    scenario_row = table_data[header_row_idx + 1] if header_row_idx + 1 < len(table_data) else None
    scenario_by_col: Dict[int, Optional[str]] = {}
    if scenario_row:
        for c_idx in header_months.keys():
            scenario_by_col[c_idx] = scenario_from_header(norm_cell(scenario_row[c_idx] if c_idx < len(scenario_row) else ''))

    metrics: List[Dict[str, Any]] = []
    context_key = f"p{page_index+1}_t{tbl_idx+1}_month_matrix"

    # Iterate data rows after the header (+ scenario row if present)
    start_data_row = header_row_idx + 1
    # If the next row looks like scenario labels, skip it
    if scenario_row:
        scen_vals = [scenario_by_col.get(c) for c in header_months.keys()]
        if any(v in {'Actual', 'Budget', 'Forecast', 'Variance', 'Prior Year'} for v in scen_vals if v):
            start_data_row = header_row_idx + 2

    for r_idx in range(start_data_row, len(table_data)):
        row = table_data[r_idx] or []
        if not row:
            continue

        line_item_raw = norm_cell(row[0] if len(row) > 0 else '')
        if not line_item_raw or len(line_item_raw) < 2:
            continue

        # Avoid obviously non-metric rows
        if line_item_raw.lower().startswith(('strictly private', 'confidential', 'appendix', 'page ')):
            continue

        emitted = 0
        for c_idx, period_label in header_months.items():
            if c_idx >= len(row):
                continue

            cell_text = norm_cell(row[c_idx])
            if not looks_numeric(cell_text):
                continue

            value_type = scenario_by_col.get(c_idx) or 'Actual'

            metrics.append({
                'context_key': context_key,
                'line_item': _clean_line_item_name(line_item_raw),
                'value': cell_text,
                'period_label': period_label,
                'period_type': 'Monthly',
                'period_scope': 'YTD' if 'ytd' in context_key.lower() else 'Period',
                'value_type': value_type,
                'frequency': 'Monthly',
                'currency': 'GBP',
                'source_file': f"page_{page_index+1}_table_{tbl_idx+1}",
                'source_page': page_index + 1,
                'source_table': tbl_idx + 1,
                'source_row': r_idx,
                'source_col': f"{period_label} {value_type}".strip(),
                'notes': 'PDF: month-matrix table',
                'extraction_method': 'pymupdf_table',
                'confidence': 0.75,
            })
            emitted += 1

        # If the row doesn't emit anything, keep scanning.
        # But if we emitted something and then hit a blank line item later, stop early.
        if emitted == 0 and len(metrics) > 0 and r_idx > start_data_row + 10:
            # Heuristic: we've likely left the numeric section
            continue

    # Require a minimum number of facts so we don't pollute DB with junk.
    if len(metrics) < 6:
        return []

    return metrics


def _identify_headers(table_data: List[List]) -> Dict[str, int]:
    """Identify column headers and their positions"""
    headers = {}
    
    for row_idx, row in enumerate(table_data[:3]):  # Check first 3 rows for headers
        for col_idx, cell in enumerate(row):
            if cell and isinstance(cell, str):
                cell_lower = cell.lower().strip()
                
                # Look for period/date indicators
                if any(period in cell_lower for period in ['feb-25', 'feb-24', 'actual', 'budget', 'prior', 'ytd']):
                    headers[f"period_{col_idx}"] = col_idx
                
                # Look for variance indicators
                if 'variance' in cell_lower or 'vs' in cell_lower:
                    headers[f"variance_{col_idx}"] = col_idx
    
    return headers


def _extract_financial_metrics_from_row(row: List, headers: Dict[str, int], row_idx: int) -> List[Dict[str, Any]]:
    """Extract individual financial metrics from a complex table row"""
    metrics = []
    
    # Find the cell with financial line items and corresponding value cells
    line_items_cell = None
    values_cells = []
    
    # Strategy: Look for the pattern where one cell has many line items and other cells have corresponding values
    for col_idx, cell in enumerate(row):
        if cell and isinstance(cell, str):
            cell_content = cell.strip()
            line_count = len([line for line in cell_content.split('\n') if line.strip()])
            
            # Check if this cell contains financial line items (many lines with financial terms)
            if (line_count > 10 and 
                '\n' in cell_content and 
                any(keyword in cell_content.lower() for keyword in ['revenue', 'profit', 'cost', 'expense', 'income', 'staff', 'gross'])):
                line_items_cell = (col_idx, cell_content)
            
            # Check if this cell contains corresponding financial values
            elif (line_count > 5 and 
                  '\n' in cell_content and 
                  _contains_multiple_financial_values(cell_content)):
                values_cells.append((col_idx, cell_content))
    
    # If we found line items and values, parse them together
    if line_items_cell and values_cells:
        metrics.extend(_parse_aligned_financial_data(line_items_cell, values_cells, headers, row_idx))
    else:
        # Fallback: treat each cell individually
        for col_idx, cell in enumerate(row):
            if cell and isinstance(cell, str):
                cell = cell.strip()
                if cell and cell not in ['', 'None', 'nan']:
                    # Format for field_mapper compatibility
                    if _looks_like_number(cell):
                        line_item = "Unknown"
                        value = cell
                    else:
                        line_item = cell
                        value = None
                    
                    metric = {
                        "line_item": line_item,
                        "value": value,
                        "period_label": None,
                        "period_type": "actual",
                        "value_type": "Actual", 
                        "frequency": "Monthly",
                        "currency": "GBP",
                        "source_file": f"page_{page_index+1}_table_{tbl_idx+1}",
                        "source_page": page_index + 1,
                        "notes": f"PDF cell: {cell[:50]}",
                        "_raw_text": cell,
                        "_column_index": col_idx
                    }
                    metrics.append(metric)
    
    return metrics


def _contains_multiple_financial_values(text: str) -> bool:
    """Check if text contains multiple financial values (numbers)"""
    import re
    lines = text.split('\n')
    value_count = 0
    for line in lines:
        if re.search(r'[\d,().-]+', line.strip()):
            value_count += 1
    return value_count >= 3


def _parse_aligned_financial_data(line_items_cell: tuple, values_cells: List[tuple], headers: Dict[str, int], row_idx: int) -> List[Dict[str, Any]]:
    """Parse line items aligned with their corresponding values"""
    metrics = []
    
    col_idx, line_items_text = line_items_cell
    line_items = [line.strip() for line in line_items_text.split('\n') if line.strip()]
    
    # Process each values column
    for values_col_idx, values_text in values_cells:
        values = [line.strip() for line in values_text.split('\n') if line.strip()]
        
        # Align line items with values
        for i, line_item in enumerate(line_items):
            if i < len(values) and values[i]:
                value = values[i]
                
                # Skip non-financial line items (headers, etc.)
                if _is_financial_line_item(line_item):
                    # Clean the line item name
                    clean_line_item = _clean_line_item_name(line_item)
                    
                    # Parse the value (might contain multiple values)
                    parsed_values = _parse_financial_value(value)
                    
                    # Create metrics for each parsed value
                    for val_idx, parsed_value in enumerate(parsed_values):
                        if parsed_value:
                            period_info = _identify_period_from_headers(values_col_idx, headers)
                            
                            # Create metric in the format expected by field_mapper
                            metric = {
                                "line_item": clean_line_item,
                                "value": parsed_value,
                                "period_label": period_info.get('period'),
                                "period_type": period_info.get('data_type', 'actual'),
                                "value_type": period_info.get('data_type', 'actual').title(),
                                "frequency": "Monthly",
                                "currency": "GBP",  # Based on £ symbol in PDF
                                "source_file": f"page_{page_index+1}_table_{tbl_idx+1}",
                                "source_page": page_index + 1,
                                "notes": f"PDF extraction: {line_item[:50]}",
                                "_raw_line_item": line_item,
                                "_raw_value": value,
                                "_column_index": values_col_idx,
                                "_value_index": val_idx
                            }
                            
                            metrics.append(metric)
    
    return metrics


def _is_financial_line_item(line_item: str) -> bool:
    """Check if a line item represents a financial metric"""
    if not line_item or len(line_item.strip()) < 2:
        return False
    
    line_lower = line_item.lower().strip()
    
    # Skip obvious headers and non-financial items
    skip_terms = ['profit and loss', 'wilson partners', 'management reports', 'statutory basis', 
                  'monthly', 'ytd', 'comparison', 'actual', 'budget', 'variance']
    
    if any(skip_term in line_lower for skip_term in skip_terms):
        return False
    
    # Include known financial terms
    financial_terms = ['revenue', 'sales', 'income', 'profit', 'loss', 'cost', 'expense', 
                      'ebitda', 'margin', 'tax', 'interest', 'depreciation', 'amortisation',
                      'staff', 'premises', 'office', 'professional', 'assets', 'liabilities']
    
    # If it contains financial terms, it's likely a financial line item
    if any(term in line_lower for term in financial_terms):
        return True
    
    # If it's a reasonable length and doesn't look like a number, it might be a line item
    return len(line_item.strip()) > 2 and not _looks_like_number(line_item)


def _clean_line_item_name(line_item: str) -> str:
    """Clean and standardize line item names"""
    cleaned = line_item.strip()
    
    # Remove common prefixes/suffixes
    cleaned = cleaned.replace('Reported ', '').replace('Adjusted ', '').replace('Proforma ', '')
    
    # Standardize common terms
    replacements = {
        'Gross profit': 'Gross Profit',
        'Operating profit': 'Operating Profit', 
        'Net profit': 'Net Profit',
        'Staff Costs': 'Staff Costs',
        'Revenue': 'Revenue'
    }
    
    for old, new in replacements.items():
        if old.lower() in cleaned.lower():
            return new
    
    return cleaned


def _parse_financial_value(value_text: str) -> List[str]:
    """Parse financial values from text, handling multiple values per cell"""
    import re
    
    # Clean the text
    cleaned = value_text.strip()
    
    # Look for financial number patterns
    # Matches: 1,234,567 or (1,234) or 1234.56 etc.
    pattern = r'[\(]?[\d,]+\.?\d*[\)]?'
    matches = re.findall(pattern, cleaned)
    
    # Filter out very small numbers (likely not main financial figures)
    filtered_matches = []
    for match in matches:
        # Remove commas for length check
        clean_match = match.replace(',', '').replace('(', '').replace(')', '')
        if len(clean_match) >= 2:  # At least 2 digits
            filtered_matches.append(match)
    
    # If we have multiple values, take the first one (usually the main figure)
    # Or return all if they seem significant
    if len(filtered_matches) == 1:
        return filtered_matches
    elif len(filtered_matches) > 1:
        # Return the first value (main figure)
        return [filtered_matches[0]]
    
    return []


def _parse_multiline_financial_data(main_cell: str, values_cells: List, headers: Dict[str, int], row_idx: int) -> List[Dict[str, Any]]:
    """Parse multi-line cell containing financial metrics"""
    metrics = []
    lines = main_cell.split('\n')
    
    # Extract line items (financial metric names)
    line_items = []
    for line in lines:
        line = line.strip()
        if line and not _looks_like_number(line):
            # This could be a financial line item
            line_items.append(line)
    
    # Try to match with values from other cells
    for values_col_idx, values_cell in values_cells:
        if values_cell and '\n' in values_cell:
            values = values_cell.split('\n')
            
            # Match line items with values
            for i, line_item in enumerate(line_items):
                if i < len(values):
                    value = values[i].strip()
                    if value and _looks_like_financial_value(value):
                        metric = {
                            "line_item": line_item.strip(),
                            "value": value,
                            "column_index": values_col_idx,
                            "raw_line_item": line_item,
                            "raw_value": value
                        }
                        
                        # Try to identify the period from headers
                        period_info = _identify_period_from_headers(values_col_idx, headers)
                        if period_info:
                            metric.update(period_info)
                        
                        metrics.append(metric)
    
    return metrics


def _extract_text_based_data(page, file_path: Path, page_index: int) -> List[Dict[str, Any]]:
    """Text-based extraction with financial pattern recognition"""
    rows = []

    try:
        # Get text from page
        text = page.get_text()

        # Also try OCR as fallback
        try:
            images = convert_from_path(str(file_path), first_page=page_index+1, last_page=page_index+1)
            ocr_text = pytesseract.image_to_string(images[0])
            # Combine both text sources
            combined_text = text + "\n" + ocr_text
        except Exception:
            combined_text = text

        # Statutory accounts: best-effort yearly Turnover/Revenue extraction
        rows.extend(_extract_accounts_yearly_turnover(combined_text, page_number=page_index + 1))

        # Prefer structured P&L extraction when present
        pl_rows = _extract_pl_statement_rows(combined_text, page_number=page_index + 1)
        if pl_rows:
            for row in pl_rows:
                row["_sheet_name"] = f"page_{page_index+1}_pl_text"
                rows.append(row)
            return rows

        # Fallback: Parse single-value financial patterns from text
        financial_patterns = _extract_financial_patterns(combined_text)

        for pattern in financial_patterns:
            pattern["_sheet_name"] = f"page_{page_index+1}_text"
            rows.append(pattern)

    except Exception as e:
        log_event("pdf_text_extract_error", {"page": page_index + 1, "error": str(e)})

    return rows



def _extract_accounts_yearly_turnover(text: str, page_number: int) -> List[Dict[str, Any]]:
    """Best-effort extraction of yearly Turnover/Revenue from statutory accounts.

    Looks for a 2-year header (e.g. 2024 / 2023) and a line starting with
    Turnover/Revenue containing 2 numeric values.

    Emits Yearly facts and lets field_mapper map Turnover -> Revenue.
    """

    import re

    if not text:
        return []

    lines = text.splitlines()

    years = None
    for line in lines[:160]:
        ys = re.findall(r"\b(20\d{2})\b", line)
        if len(ys) >= 2:
            years = [ys[0], ys[1]]
            break

    if not years:
        return []

    money_pat = re.compile(r"\b\d{1,3}(?:,\d{3})+\b|\b\d+\b")

    units = _detect_units_label(text)

    out: List[Dict[str, Any]] = []

    def parse_int(s: str) -> Optional[int]:
        try:
            return int(s.replace(',', ''))
        except Exception:
            return None

    def is_junk_value(v: str) -> bool:
        vv = v.strip().replace(',', '')
        # reject obvious placeholders like 0/00/000
        return vv in {'0', '00', '000'}

    for line in lines:
        if not re.match(r"^\s*(Turnover|Revenue)\b", line, re.IGNORECASE):
            continue

        nums = money_pat.findall(line)
        if len(nums) < 2:
            continue

        # Prefer comma-formatted values (accounts usually show thousands separators).
        comma_vals = [n for n in nums if ',' in n and not is_junk_value(n)]
        plain_vals = [n for n in nums if ',' not in n and not is_junk_value(n)]

        candidates = comma_vals if len(comma_vals) >= 2 else [n for n in nums if not is_junk_value(n)]
        if len(candidates) < 2:
            continue

        # Prefer values consistent with declared units.
        if units == '£000':
            # in £000, values are usually 4-6 digits (with commas). pick the smallest two non-junk.
            candidates_sorted = sorted(candidates, key=lambda s: (len(s.replace(',', '')), s.count(',')))
            vals = candidates_sorted[:2]
        else:
            vals = candidates[-2:]

        # Basic sanity: values should be of similar order of magnitude (same statement columns).
        v1 = parse_int(vals[0])
        v2 = parse_int(vals[1])
        if v1 is None or v2 is None or v1 == 0 or v2 == 0:
            continue
        ratio = max(v1, v2) / min(v1, v2)
        if ratio > 20:
            continue

        for year, value in zip(years, vals):
            notes = 'PDF: accounts income statement (yearly)'
            if units:
                notes = f"{notes} [units={units}]"

            out.append({
                'line_item': 'Turnover',
                'value': value,
                'value_type': 'Actual',
                'period_label': year,
                'period_type': 'Yearly',
                'period_scope': 'Period',
                'frequency': 'Yearly',
                'currency': 'GBP' if '£' in text else None,
                'source_page': page_number,
                'source_col': units or None,
                'context_key': 'accounts_income_statement_yearly',
                'notes': notes,
                'extraction_method': 'text_accounts',
                'confidence': 0.55,
            })

        # Stop after first plausible hit per page
        if out:
            break

    return out



def _extract_pl_statement_rows(text: str, page_number: int) -> List[Dict[str, Any]]:
    """Extract structured P&L rows (Actual/Budget/Prior/Variances) from text.

    This targets board-pack style monthly P&L tables where each line has:
    Line Item + 5 numeric columns (Actual, Budget, Prior Year, Var to Budget, Var to Prior).
    """
    import re

    month_map = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    }

    # Currency (best-effort)
    currency = 'GBP' if '£' in text else 'USD' if '$' in text else None

    # Period scope hint
    ytd_hint = 'ytd' in text.lower() or 'year to date' in text.lower()

    # Period label (best-effort, based on title like "February 2025")
    period_label = None
    m = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', text, re.IGNORECASE)
    if m:
        month = month_map[m.group(1).lower()]
        year = int(m.group(2))
        period_label = f"{year}-{month:02d}"

    value_types = [
        'Actual',
        'Budget',
        'Prior Year',
        'Variance to budget',
        'Variance to prior year',
    ]

    # Heuristic: only start parsing after we see the P&L section header.
    lines = [ln.strip() for ln in text.split("\n")] 
    try:
        start_idx = next(i for i, ln in enumerate(lines) if 'PROFIT AND LOSS' in ln.upper())
    except StopIteration:
        start_idx = 0

    number_re = re.compile(r'\(?-?[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?\)?')

    rows: List[Dict[str, Any]] = []
    for ln in lines[start_idx:]:
        if not ln or len(ln) < 3:
            continue

        # Skip obvious headers
        if any(k in ln.upper() for k in ['PROFIT AND LOSS', 'STATUTORY BASIS', 'MONTHLY P&L', 'VARIANCE', 'ACTUAL', 'BUDGET', 'PRIOR', '£']):
            continue

        nums = number_re.findall(ln)
        if len(nums) < 5:
            continue

        # Line item is the part before the first number
        first_num_pos = ln.find(nums[0])
        if first_num_pos <= 0:
            continue

        line_item = ln[:first_num_pos].strip()
        if not line_item or len(line_item) < 2:
            continue

        # Take first 5 numeric columns (ignore any trailing % etc.)
        cols = nums[:5]
        for vt, val in zip(value_types, cols):
            row = {
                'line_item': line_item,
                'value': val,
                'value_type': vt,
                'frequency': 'Monthly',
                'period_type': 'Monthly',
                'period_scope': 'YTD' if ytd_hint else 'Period',
                'source_page': page_number,
                'notes': 'PDF: P&L table' + (' [ytd]' if ytd_hint else ''),
                'extraction_method': 'text_pl_table',
                'confidence': 0.5,
            }
            if currency:
                row['currency'] = currency
            if period_label:
                row['period_label'] = period_label
            rows.append(row)

    return rows

def _extract_financial_patterns(text: str) -> List[Dict[str, Any]]:
    """Extract financial patterns from raw text using regex"""
    import re
    patterns = []
    
    # Common financial line items
    financial_terms = [
        'revenue', 'sales', 'income', 'profit', 'loss', 'cost', 'expense', 
        'ebitda', 'margin', 'tax', 'interest', 'depreciation', 'amortisation',
        'gross profit', 'operating profit', 'net profit'
    ]
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if len(line) < 3:
            continue
            
        # Look for patterns like "Revenue 1,234,567"
        for term in financial_terms:
            if term.lower() in line.lower():
                # Extract numbers from the line
                numbers = re.findall(r'[\d,]+\.?\d*', line)
                if numbers:
                    # Take the largest number (likely the main value)
                    largest_num = max(numbers, key=lambda x: len(x.replace(',', '')))
                    patterns.append({
                        "line_item": term.title(),
                        "value": largest_num,
                        "raw_text": line,
                        "value_type": "Actual",
                        "period_scope": "YTD" if ("ytd" in line.lower() or "year to date" in line.lower()) else "Period",
                        "notes": "PDF: text pattern" + (" [ytd]" if ("ytd" in line.lower() or "year to date" in line.lower()) else ""),
                        "extraction_method": "text_pattern",
                        "confidence": 0.25,
                    })
                break
    
    return patterns


# Helper functions
def _looks_like_financial_data(text: str) -> bool:
    """Check if text looks like financial data"""
    import re
    # Look for numbers with commas, parentheses (negative), or decimal points
    return bool(re.search(r'[\d,().-]+', text)) and len(text.strip()) > 2


def _looks_like_number(text: str) -> bool:
    """Check if text looks like a number"""
    import re
    text = text.strip()
    # Match patterns like: 1234, 1,234, (1234), 1234.56, etc.
    return bool(re.match(r'^[(),\d.,\s-]+$', text))


def _looks_like_financial_value(text: str) -> bool:
    """Check if text looks like a financial value"""
    import re
    text = text.strip()
    # Match financial number patterns
    return bool(re.search(r'\d+[,\d]*\.?\d*', text)) or '(' in text


def _identify_period_from_headers(col_idx: int, headers: Dict[str, int]) -> Dict[str, str]:
    """Identify period information from column headers"""
    period_info = {}
    
    for header_key, header_col in headers.items():
        if header_col == col_idx:
            if 'feb-25' in header_key.lower():
                period_info['period'] = '2025-02'
            elif 'feb-24' in header_key.lower():
                period_info['period'] = '2024-02'
            elif 'actual' in header_key.lower():
                period_info['data_type'] = 'actual'
            elif 'budget' in header_key.lower():
                period_info['data_type'] = 'budget'
            elif 'variance' in header_key.lower():
                period_info['data_type'] = 'variance'
    
    return period_info


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


def ingest_pdf(file_path: Union[str, Path], company_id: int = 1, document_id: int = None) -> Dict[str, Any]:
    """PDF ingestion.

    Also persists raw extracted facts (with coordinates) when document_id is provided.

    Notes:
    - For multi-pack ingestion, we apply a best-effort monthly period hint from the original
      filename when a row lacks a period label (keeps the system useful without LLMs).
    """
    file_path = Path(file_path)
    log_event("pdf_ingestion_started", {"file_path": str(file_path), "company_id": company_id})

    original_filename = None
    if document_id is not None:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT original_filename FROM documents WHERE id=%s", (document_id,))
                    r = cur.fetchone()
                    original_filename = r[0] if r else None
        except Exception:
            original_filename = None

    period_hint = _period_hint_from_filename(original_filename or file_path.name)

    # 1) Extraction
    raw_rows = extract_pdf_rows(file_path)

    # OCR fallback: if extraction is empty, try making a searchable PDF and re-extract.
    ocr_pdf_path: Optional[Path] = None
    if not raw_rows:
        ocr_pdf_path = _ocr_to_searchable_pdf(file_path)
        if ocr_pdf_path is not None:
            raw_rows = extract_pdf_rows(ocr_pdf_path)

    # Text fallback: if we still don't have monthly Revenue candidates, try a layout-preserving
    # text extraction and parse month-column rows.
    if raw_rows and not _has_monthly_revenue_candidate(raw_rows):
        try:
            supplemental = _supplement_monthly_series_via_pdftotext(file_path)
            if supplemental:
                raw_rows.extend(supplemental)
        except Exception:
            pass

    if not raw_rows:
        return {
            "status": "no_data",
            "file_path": str(file_path),
            "ingested": 0,
            "skipped": 0,
            "errors": 0,
            "ocr_attempted": ocr_pdf_path is not None
        }

    # 2) Field Mapping
    mapped_rows = []
    map_errors = 0
    for idx, row in enumerate(raw_rows, start=1):
        try:
            if period_hint and not row.get('period_label'):
                row['period_label'] = period_hint
            mapped = map_and_filter_row(row)
            if mapped:
                mapped_rows.append(mapped)
        except Exception as e:
            log_event("pdf_map_error", {"row": idx, "error": str(e)})
            map_errors += 1

    # 3) Raw persistence (audit layer)
    raw_inserted = 0
    raw_errors = 0
    if document_id is not None:
        raw_result = persist_raw_facts(raw_rows, document_id=document_id, company_id=company_id)
        raw_inserted = raw_result.get("inserted", 0)
        raw_errors = raw_result.get("errors", 0)

    # 4) Normalization
    normalized, norm_errors, rejected = normalize_data(mapped_rows, str(file_path), company_id, document_id)

    # 4b) Quality gate: persist a structured status snapshot onto the document.
    if document_id is not None:
        try:
            from psycopg2.extras import Json

            with get_db_connection() as conn:
                qr = assess_revenue_analyst_quality_from_db(conn=conn, company_id=company_id)
                vr = validate_company_monthly_series(conn=conn, company_id=company_id)
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE documents SET metadata = COALESCE(metadata, '{}'::jsonb) || %s WHERE id = %s",
                        (Json({"quality_report": qr.to_dict(), "validation_report": vr.to_dict()}), document_id),
                    )
                    conn.commit()
        except Exception:
            pass

    # Persist rejects (best-effort) so we don't drop data silently.
    if document_id is not None and rejected:
        try:
            from rejections_persistence import persist_fact_rejections

            persist_fact_rejections(rejected, company_id=company_id, document_id=document_id)
        except Exception:
            pass

    # 5) Persistence
    if not normalized:
        # No data to persist after normalization.
        # Try OCR once here too (covers cases where extraction produced rows but no period/value labels).
        log_event("pdf_no_data_after_normalization", {
            "file_path": str(file_path),
            "raw_rows": len(raw_rows),
            "mapped_rows": len(mapped_rows),
            "normalization_errors": norm_errors
        })

        ocr_pdf_path = _ocr_to_searchable_pdf(file_path)
        if ocr_pdf_path is not None:
            raw_rows2 = extract_pdf_rows(ocr_pdf_path)
            mapped_rows2 = []
            map_errors2 = 0
            for idx, row in enumerate(raw_rows2, start=1):
                try:
                    if period_hint and not row.get('period_label'):
                        row['period_label'] = period_hint
                    mapped = map_and_filter_row(row)
                    if mapped:
                        mapped_rows2.append(mapped)
                except Exception as e:
                    log_event("pdf_map_error", {"row": idx, "error": str(e), "ocr": True})
                    map_errors2 += 1

            normalized2, norm_errors2, rejected2 = normalize_data(mapped_rows2, str(file_path), company_id, document_id)

            if document_id is not None and rejected2:
                try:
                    from rejections_persistence import persist_fact_rejections

                    persist_fact_rejections(rejected2, company_id=company_id, document_id=document_id)
                except Exception:
                    pass
            if normalized2:
                raw_rows = raw_rows2
                mapped_rows = mapped_rows2
                map_errors = map_errors2
                normalized = normalized2
                norm_errors = norm_errors2

        if not normalized:
            return {
                "status": "no_data",
                "file_path": str(file_path),
                "ingested": 0,
                "skipped": len(raw_rows),
                "errors": map_errors + norm_errors
            }
    
    # Ensure the persisted rows use the caller-provided company_id (not any default from normalization)
    for row in normalized:
        row["company_id"] = company_id

    # Persist per-period since persist_data expects a single period_id
    from collections import defaultdict

    grouped_by_period: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        grouped_by_period[row["period_id"]].append(row)

    total_inserted = 0
    total_skipped = 0
    total_errors = 0

    for period_id, period_rows in grouped_by_period.items():
        persist_result = persist_data(period_rows, company_id, period_id)
        total_inserted += int(persist_result.get("inserted", 0) or 0)
        total_skipped += int(persist_result.get("skipped", 0) or 0)
        total_errors += int(persist_result.get("errors", 0) or 0)

    summary = {
        "file_path": str(file_path),
        "company_id": company_id,
        "document_id": document_id,
        "rows_extracted": len(raw_rows),
        "rows_mapped": len(mapped_rows),
        "map_errors": map_errors,
        "raw_persisted": raw_inserted,
        "raw_persist_errors": raw_errors,
        "rows_normalized": len(normalized),
        "norm_errors": norm_errors,
        "persisted": total_inserted,
        "skipped": total_skipped,
        "persist_errors": total_errors,
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
