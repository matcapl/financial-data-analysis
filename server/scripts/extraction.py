# server/scripts/extraction.py - File reading layer consistent with existing patterns
import pandas as pd
import os
import sys
from utils import log_event


class FileExtractor:
    """Handles file reading for various formats, consistent with existing ingest_xlsx.py patterns"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_extension = os.path.splitext(file_path)[1].lower()
        
    def extract(self) -> list:
        """Extract data from file and return list of dictionaries (raw rows)"""
        
        log_event("extraction_started", {
            "file_path": self.file_path,
            "file_type": self.file_extension
        })
        
        try:
            if self.file_extension == ".xlsx":
                df = pd.read_excel(self.file_path)
                log_event("file_read_success", {"type": "xlsx", "file_path": self.file_path})
            elif self.file_extension == ".csv":
                try:
                    df = pd.read_csv(self.file_path, encoding="utf-8")
                    log_event("file_read_success", {"type": "csv-utf8", "file_path": self.file_path})
                except UnicodeDecodeError:
                    df = pd.read_csv(self.file_path, encoding="latin-1")  
                    log_event("file_read_success", {"type": "csv-latin1", "file_path": self.file_path})
            else:
                raise ValueError(f"Unsupported file type: {self.file_extension}")
                
            # Convert to list of dictionaries (same as existing ingest_xlsx.py)
            raw_rows = []
            for idx, row in df.iterrows():
                raw_dict = row.to_dict()
                raw_dict['_row_number'] = idx + 1  # Add row tracking
                raw_rows.append(raw_dict)
                
            log_event("extraction_completed", {
                "file_path": self.file_path,
                "rows_extracted": len(raw_rows),
                "columns_found": list(df.columns)
            })
            
            return raw_rows
            
        except Exception as e:
            log_event("extraction_failed", {
                "file_path": self.file_path,
                "error": str(e)
            })
            raise


def extract_data(file_path: str) -> list:
    """Convenience function for backward compatibility"""
    extractor = FileExtractor(file_path)
    return extractor.extract()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extraction.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    try:
        rows = extract_data(file_path)
        print(f"Extracted {len(rows)} rows from {file_path}")
        print(f"Sample row: {rows[0] if rows else 'No data'}")
    except Exception as e:
        print(f"Extraction failed: {e}")
        sys.exit(1)