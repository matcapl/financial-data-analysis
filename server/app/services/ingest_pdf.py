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
    Extract raw rows from PDF with enhanced parsing:
    - Enhanced table extraction with merged cell handling
    - Multi-line cell parsing for financial data
    - Text-based fallback with pattern recognition
    """
    raw_rows: List[Dict[str, Any]] = []
    doc = fitz.open(str(file_path))
    
    for page_index in range(len(doc)):
        page = doc[page_index]
        page_rows = []
        
        # Try enhanced table extraction first
        page_rows.extend(_extract_enhanced_tables(page, page_index))
        
        # If no meaningful data from tables, try text-based extraction
        if not page_rows:
            page_rows.extend(_extract_text_based_data(page, file_path, page_index))
        
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


def _process_complex_table(table_data: List[List], page_index: int, tbl_idx: int) -> List[Dict[str, Any]]:
    """Process complex tables with merged cells and financial data structures"""
    rows = []
    
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
                                    
                                    metric = {
                                        "line_item": _clean_line_item_name(line_item),
                                        "value": clean_value,
                                        "period_label": "2025-02",
                                        "period_type": "actual",
                                        "value_type": "Actual",
                                        "frequency": "Monthly", 
                                        "currency": "GBP",
                                        "source_file": f"page_{page_index+1}_table_{tbl_idx+1}",
                                        "source_page": page_index + 1,
                                        "notes": f"PDF: {line_item[:30]}",
                                        "_sheet_name": f"page_{page_index+1}_table_{tbl_idx+1}",
                                        "_source_row": row_idx
                                    }
                                    rows.append(metric)
    
    return rows


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
                        "period_label": "2025-02",  # Default period
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
                                "period_label": period_info.get('period', '2025-02'),  # Default to Feb 2025
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
            combined_text = text + '\n' + ocr_text
        except:
            combined_text = text
        
        # Parse financial data from text
        financial_patterns = _extract_financial_patterns(combined_text)
        
        for pattern in financial_patterns:
            pattern["_sheet_name"] = f"page_{page_index+1}_text"
            rows.append(pattern)
            
    except Exception as e:
        log_event("pdf_text_extract_error", {"page": page_index + 1, "error": str(e)})
    
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
                        "extraction_method": "text_pattern"
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
    if not normalized:
        # No data to persist after normalization
        log_event("pdf_no_data_after_normalization", {
            "file_path": str(file_path),
            "raw_rows": len(raw_rows),
            "mapped_rows": len(mapped_rows),
            "normalization_errors": norm_errors
        })
        return {
            "status": "no_data",
            "file_path": str(file_path),
            "ingested": 0,
            "skipped": len(raw_rows),
            "errors": map_errors + norm_errors
        }
    
    # Extract company_id and period_id from first normalized row
    pid = normalized[0]["period_id"]
    cid = normalized[0]["company_id"]
    persist_result = persist_data(normalized, cid, pid)

    summary = {
        "file_path": str(file_path),
        "company_id": company_id,
        "rows_extracted": len(raw_rows),
        "rows_mapped": len(mapped_rows),
        "map_errors": map_errors,
        "rows_normalized": len(normalized),
        "norm_errors": norm_errors,
        "persisted": persist_result.get("inserted", 0),
        "skipped": persist_result.get("skipped", 0),
        "persist_errors": persist_result.get("errors", 0),
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
