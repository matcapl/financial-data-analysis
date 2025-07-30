import pandas as pd
from datetime import datetime
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
        """
        CRITICAL FIX: Proper file type handling
        - Use pd.read_excel() for .xlsx files
        - Use pd.read_csv() for .csv files with encoding detection
        - Handle both file types appropriately
        """
        log_event("ingestion_started", {"file_path": self.file_path, "company_id": self.company_id})
        
        try:
            # Determine file type and read accordingly
            file_ext = os.path.splitext(self.file_path)[1].lower()
            
            if file_ext == '.xlsx':
                # Read Excel file
                try:
                    df = pd.read_excel(self.file_path)
                    log_event("file_read_success", {"type": "xlsx", "file_path": self.file_path})
                except Exception as e:
                    log_event("file_read_error", {"type": "xlsx", "error": str(e), "file_path": self.file_path})
                    raise Exception(f"Failed to read Excel file: {str(e)}")
            
            elif file_ext == '.csv':
                # Read CSV file with encoding detection
                try:
                    # Try UTF-8 first
                    df = pd.read_csv(self.file_path, encoding='utf-8')
                    log_event("file_read_success", {"type": "csv", "encoding": "utf-8", "file_path": self.file_path})
                except UnicodeDecodeError:
                    try:
                        # Try latin-1 encoding
                        df = pd.read_csv(self.file_path, encoding='latin-1')
                        log_event("file_read_success", {"type": "csv", "encoding": "latin-1", "file_path": self.file_path})
                    except Exception as e:
                        try:
                            # Try cp1252 encoding (Windows)
                            df = pd.read_csv(self.file_path, encoding='cp1252')
                            log_event("file_read_success", {"type": "csv", "encoding": "cp1252", "file_path": self.file_path})
                        except Exception as e:
                            log_event("file_read_error", {"type": "csv", "error": str(e), "file_path": self.file_path})
                            raise Exception(f"Failed to read CSV file with any encoding: {str(e)}")
            else:
                raise Exception(f"Unsupported file type: {file_ext}. Only .xlsx and .csv files are supported.")
            
            # Normalize column names
            df.columns = [col.lower().strip() for col in df.columns]
            
            log_event("file_processing_started", {
                "rows_found": len(df),
                "columns_found": list(df.columns),
                "file_path": self.file_path
            })
            
            # Process each row
            for index, row in df.iterrows():
                try:
                    self._process_row(row, index + 1)
                except Exception as row_error:
                    self.error_count += 1
                    log_event("row_processing_error", {
                        "row_number": index + 1,
                        "error": str(row_error),
                        "row_data": row.to_dict()
                    })
                    continue
            
            # Commit all changes
            self.conn.commit()
            
            # Prepare summary
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
        """Process a single row of data with enhanced validation"""
        try:
            # Check for required fields
            if pd.isna(row.get("line_item")) or pd.isna(row.get("period_label")):
                self.skipped_count += 1
                log_event("row_skipped", {
                    "row_number": row_number,
                    "reason": "Missing line_item or period_label"
                })
                return
            
            line_item = str(row["line_item"]).strip()
            
            # Validate line item (case insensitive)
            valid_line_items = ["Revenue", "Gross Profit", "EBITDA"]
            line_item_normalized = None
            for valid_item in valid_line_items:
                if line_item.lower() == valid_item.lower():
                    line_item_normalized = valid_item
                    break
            
            if not line_item_normalized:
                self.skipped_count += 1
                log_event("row_skipped", {
                    "row_number": row_number,
                    "reason": f"Invalid line_item: {line_item}. Valid items: {valid_line_items}"
                })
                return
            
            # Parse period information
            period_info = parse_period(row["period_label"], row.get("period_type", "Monthly"))
            
            with self.conn.cursor() as cur:
                # Get line item ID
                cur.execute("SELECT id FROM line_item_definitions WHERE name = %s", (line_item_normalized,))
                line_item_result = cur.fetchone()
                if not line_item_result:
                    self.error_count += 1
                    log_event("line_item_not_found", {
                        "row_number": row_number,
                        "line_item": line_item_normalized
                    })
                    return
                line_item_id = line_item_result[0]

                # Get or create period
                cur.execute(
                    "SELECT id FROM periods WHERE period_type = %s AND period_label = %s",
                    (period_info["type"], period_info["label"])
                )
                period_result = cur.fetchone()
                if not period_result:
                    cur.execute(
                        "INSERT INTO periods (period_type, period_label, start_date, end_date, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                        (period_info["type"], period_info["label"], period_info["start_date"], 
                         period_info["end_date"], datetime.now(), datetime.now())
                    )
                    period_id = cur.fetchone()[0]
                else:
                    period_id = period_result[0]

                # Prepare data for insertion
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
                
                # Create hash for deduplication
                data["hash"] = hash_datapoint(
                    data["company_id"], 
                    data["period_id"], 
                    line_item_normalized, 
                    data["value_type"], 
                    data["frequency"]
                )
                
                # Check for duplicates
                cur.execute("SELECT id FROM financial_metrics WHERE hash = %s", (data["hash"],))
                if cur.fetchone():
                    self.skipped_count += 1
                    log_event("duplicate_skipped", {
                        "row_number": row_number,
                        "hash": data["hash"]
                    })
                    return
                
                # Insert the financial metric
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
                    "row_number": row_number,
                    "line_item": line_item_normalized,
                    "period_label": period_info["label"],
                    "value": data["value"]
                })
                
        except Exception as e:
            self.error_count += 1
            log_event("row_processing_error", {
                "row_number": row_number,
                "error": str(e),
                "row_data": row.to_dict() if hasattr(row, 'to_dict') else str(row)
            })
            raise

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_xlsx.py <file_path> [company_id]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    # Verify file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    print(f"Enhanced XLSX/CSV ingestion starting for file: {file_path}")
    
    with XLSXIngester(file_path, company_id) as ingester:
        result = ingester.process_file()
        print(f"Enhanced XLSX/CSV ingestion result: {result}")