import fitz
import pytesseract
from pdf2image import convert_from_path
import pandas as pd
import psycopg2
import sys
import os
import re
from datetime import datetime
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent))
from utils import hash_datapoint, log_event, get_db_connection, clean_numeric_value, parse_period
from field_mapper import map_and_filter_row


class PDFIngester:
    def __init__(self, file_path: str, company_id: int = 1):
        """
        Enhanced PDF Ingester - Phase 1 Critical Fix
        
        Key improvements:
        1. Case-insensitive metric identification
        2. Enhanced regex patterns for better number extraction
        3. Improved table header matching
        4. Better handling of mixed-case labels like "Adjusted EBITDA"
        5. More robust number parsing including parentheses as negatives
        6. Integration with field_mapper for filtering only target metrics
        """
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
            # Try table extraction first
            tables = page.find_tables()
            if tables:
                log_event("tables_found", {"page_number": page_num, "table_count": len(tables)})
                for table_idx, table in enumerate(tables):
                    df = pd.DataFrame(table.extract())
                    self._process_table(df, page_num, table_idx)
            else:
                # Fallback to OCR text extraction
                log_event("no_tables_found_using_ocr", {"page_number": page_num})
                images = convert_from_path(self.file_path, first_page=page_num, last_page=page_num)
                text = pytesseract.image_to_string(images[0])
                self._process_text(text, page_num)
                
        except Exception as e:
            self.error_count += 1
            log_event("page_processing_error", {"page_number": page_num, "error": str(e)})


    def _process_table(self, df, page_num, table_idx):
        """Enhanced table processing with field mapping integration"""
        # Clean column names - preserve case for better matching
        df.columns = [str(col).strip() for col in df.columns]
        original_columns = df.columns.tolist()
        
        log_event("table_processing", {
            "page_number": page_num, 
            "table_index": table_idx,
            "columns": original_columns,
            "rows": len(df)
        })
        
        for row_idx, row in df.iterrows():
            # Get row label (first column)
            row_label = str(row.iloc[0]).strip() if len(row) > 0 else ""
            if not row_label or row_label.lower() in ['nan', 'none', '']:
                continue
                
            # Process each data column
            for col_idx, col in enumerate(df.columns[1:], 1):  # Skip first column (labels)
                if col_idx >= len(row):
                    continue
                    
                cell_value = row.iloc[col_idx] if col_idx < len(row) else None
                value = self._extract_number(cell_value)
                
                if value is None:
                    continue
                
                # Enhanced period parsing with column header context
                period_info = self._parse_period_from_header(col, page_num, table_idx)
                
                # Create raw row dict for field mapping
                raw_row = {
                    "line_item": row_label,
                    "period_label": period_info["label"],
                    "period_type": period_info["type"],
                    "value_type": "Actual",
                    "frequency": period_info["type"],
                    "value": value,
                    "currency": "USD",
                    "source_file": os.path.basename(self.file_path),
                    "source_page": page_num,
                    "notes": f"Table {table_idx + 1}, Row '{row_label}', Column '{col}'"
                }
                
                # Apply field mapping and filtering
                mapped = map_and_filter_row(raw_row)
                if mapped is None:
                    continue
                
                # Insert the mapped row
                self._insert_mapped_metric(mapped, page_num)


    def _process_text(self, text, page_num):
        """Enhanced text processing with field mapping integration"""
        lines = text.split('\n')
        current_metric = None
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Extract numbers from the line
            numbers = self._extract_numbers_from_line(line)
            
            for num_value in numbers:
                # Try to infer period from context
                period_info = self._infer_period_from_context(line, page_num)
                
                # Create raw row dict for field mapping
                raw_row = {
                    "line_item": line,
                    "period_label": period_info["label"],
                    "period_type": period_info["type"],
                    "value_type": "Actual",
                    "frequency": period_info["type"],
                    "value": num_value,
                    "currency": "USD",
                    "source_file": os.path.basename(self.file_path),
                    "source_page": page_num,
                    "notes": f"Text line {line_idx + 1}: '{line[:50]}...'"
                }
                
                # Apply field mapping and filtering
                mapped = map_and_filter_row(raw_row)
                if mapped is None:
                    continue
                
                # Insert the mapped row
                self._insert_mapped_metric(mapped, page_num)


    def _insert_mapped_metric(self, mapped_row, page_num):
        """Insert a mapped and filtered metric row"""
        try:
            with self.conn.cursor() as cur:
                # Get line item ID
                cur.execute("SELECT id FROM line_item_definitions WHERE name = %s", (mapped_row["line_item"],))
                line_item_result = cur.fetchone()
                if not line_item_result:
                    self.error_count += 1
                    log_event("line_item_not_found", {"line_item": mapped_row["line_item"]})
                    return
                line_item_id = line_item_result[0]

                # Parse period
                period_info = parse_period(mapped_row["period_label"], mapped_row.get("period_type", "Monthly"))
                if not period_info:
                    period_info = {
                        "type": mapped_row.get("period_type", "Monthly"),
                        "label": mapped_row["period_label"],
                        "start_date": None,
                        "end_date": None
                    }

                # Get or create period
                cur.execute(
                    "SELECT id FROM periods WHERE period_type = %s AND period_label = %s",
                    (period_info["type"], period_info["label"])
                )
                period = cur.fetchone()
                if not period:
                    cur.execute(
                        "INSERT INTO periods (period_type, period_label, start_date, end_date, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                        (period_info["type"], period_info["label"], period_info["start_date"], 
                         period_info["end_date"], datetime.now(), datetime.now())
                    )
                    period_id = cur.fetchone()[0]
                else:
                    period_id = period[0]

                # Coerce source_page to integer
                try:
                    source_page = int(mapped_row.get("source_page", page_num))
                except (TypeError, ValueError):
                    source_page = page_num

                # Prepare data for insertion
                data = {
                    "company_id": self.company_id,
                    "period_id": period_id,
                    "line_item_id": line_item_id,
                    "value_type": mapped_row.get("value_type", "Actual"),
                    "frequency": mapped_row.get("frequency", period_info["type"]),
                    "value": clean_numeric_value(mapped_row.get("value")),
                    "currency": mapped_row.get("currency", "USD"),
                    "source_file": mapped_row.get("source_file", os.path.basename(self.file_path)),
                    "source_page": source_page,
                    "source_type": "Raw",
                    "notes": mapped_row.get("notes", "")
                }
                
                data["hash"] = hash_datapoint(data["company_id"], data["period_id"], 
                                            mapped_row["line_item"], data["value_type"], data["frequency"])

                # Check for duplicates
                cur.execute("SELECT id FROM financial_metrics WHERE hash = %s", (data["hash"],))
                if cur.fetchone():
                    self.skipped_count += 1
                    log_event("duplicate_skipped", {"hash": data["hash"]})
                    return

                # Insert the metric
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
                log_event("metric_inserted", {
                    "line_item": mapped_row["line_item"],
                    "period_label": period_info["label"],
                    "value": data["value"],
                    "source": mapped_row.get("notes", "")
                })
                
        except Exception as e:
            self.error_count += 1
            log_event("insert_error", {"error": str(e), "mapped_row": mapped_row})


    def _extract_number(self, cell_value):
        """Enhanced number extraction with better formatting support"""
        if cell_value is None or pd.isna(cell_value):
            return None
            
        text = str(cell_value).strip()
        if not text or text.lower() in ['nan', 'none', '', '-']:
            return None
            
        # Handle parentheses as negative numbers: (1,234) -> -1234
        is_negative = False
        if text.startswith('(') and text.endswith(')'):
            is_negative = True
            text = text[1:-1]  # Remove parentheses
        
        # Remove currency symbols and other non-numeric characters except digits, decimal points, commas, and minus signs
        cleaned = re.sub(r'[^\d\.\,\-]', '', text)
        
        # Handle comma-separated thousands
        cleaned = cleaned.replace(',', '')
        
        try:
            value = float(cleaned)
            return -value if is_negative else value
        except (ValueError, TypeError):
            return None


    def _extract_numbers_from_line(self, line):
        """Extract all numbers from a text line"""
        # Enhanced regex to capture numbers with various formats
        number_patterns = [
            r'\(\s*[\d,]+\.?\d*\s*\)',  # Parentheses format: (1,234.56)
            r'-?\s*[\d,]+\.?\d*',       # Regular format: -1,234.56 or 1234
        ]
        
        numbers = []
        for pattern in number_patterns:
            matches = re.findall(pattern, line)
            for match in matches:
                value = self._extract_number(match)
                if value is not None:
                    numbers.append(value)
        
        return numbers


    def _parse_period_from_header(self, column_header, page_num, table_idx):
        """Enhanced period parsing from table column headers"""
        header = str(column_header).strip()
        
        # Common header patterns
        if any(word in header.lower() for word in ['actual', 'ytd', 'current']):
            period_type = "YTD"
        elif any(word in header.lower() for word in ['budget', 'forecast', 'plan']):
            period_type = "Budget"
        elif any(word in header.lower() for word in ['prior', 'previous', 'last year', 'py']):
            period_type = "Prior Year"
        else:
            period_type = "Monthly"
        
        # Try to extract specific period from header
        period_label = f"{header} (Page {page_num}, Table {table_idx + 1})"
        
        return {
            "type": period_type,
            "label": period_label,
            "start_date": None,
            "end_date": None
        }


    def _infer_period_from_context(self, line, page_num):
        """Infer period information from text context"""
        line_lower = line.lower()
        
        # Look for month indicators
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        
        found_month = None
        for month in months:
            if month in line_lower:
                found_month = month
                break
        
        if found_month:
            period_label = f"{found_month.title()} 2025"
            period_type = "Monthly"
        else:
            period_label = f"Unknown (Page {page_num})"
            period_type = "Monthly"
        
        return {
            "type": period_type,
            "label": period_label,
            "start_date": None,
            "end_date": None
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_pdf.py <file_path> [company_id]")
        sys.exit(1)
        
    file_path = sys.argv[1]
    company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    with PDFIngester(file_path, company_id) as ingester:
        result = ingester.process_file()
        print(f"Enhanced PDF ingestion result: {result}")
