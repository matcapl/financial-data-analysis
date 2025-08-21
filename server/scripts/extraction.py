# server/scripts/extraction.py
import pandas as pd
import openpyxl
from pathlib import Path
from typing import List, Dict, Any
from utils import log_event

def extract_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract data from Excel files (.xlsx, .xls) and return as list of dictionaries.
    Handles multiple sheets, merged cells, and various data formats.
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        extension = file_path.suffix.lower()
        if extension not in ['.xlsx', '.xls']:
            raise ValueError(f"Unsupported file type: {extension}")
        
        log_event("extraction_started", {
            "file_path": str(file_path),
            "file_size": file_path.stat().st_size,
            "file_type": extension
        })
        
        # Read all sheets from the Excel file
        excel_file = pd.ExcelFile(file_path, engine='openpyxl' if extension == '.xlsx' else 'xlrd')
        all_data = []
        
        for sheet_name in excel_file.sheet_names:
            try:
                # Read sheet with minimal processing to preserve raw data
                df = pd.read_excel(
                    file_path, 
                    sheet_name=sheet_name,
                    header=0,  # Assume first row contains headers
                    dtype=str,  # Read everything as string initially
                    na_filter=False  # Don't convert empty cells to NaN
                )
                
                if df.empty:
                    log_event("sheet_empty", {"sheet": sheet_name})
                    continue
                
                # Clean column names - remove extra whitespace and newlines
                df.columns = [str(col).strip().replace('\n', ' ').replace('\r', ' ') for col in df.columns]
                
                # Convert DataFrame to list of dictionaries
                sheet_data = []
                for idx, row in df.iterrows():
                    row_dict = {}
                    for col in df.columns:
                        value = row[col]
                        # Clean and normalize cell values
                        if pd.isna(value) or value == '':
                            row_dict[col] = None
                        else:
                            # Convert to string and clean
                            cleaned_value = str(value).strip()
                            if cleaned_value == '' or cleaned_value.lower() in ['nan', 'none', 'null']:
                                row_dict[col] = None
                            else:
                                row_dict[col] = cleaned_value
                    
                    # Only include rows that have at least some data
                    if any(v is not None for v in row_dict.values()):
                        # Add metadata
                        row_dict['_sheet_name'] = sheet_name
                        row_dict['_row_index'] = idx + 2  # +2 because Excel is 1-indexed and we have header
                        sheet_data.append(row_dict)
                
                all_data.extend(sheet_data)
                
                log_event("sheet_extracted", {
                    "sheet": sheet_name,
                    "rows": len(sheet_data),
                    "columns": list(df.columns)
                })
                
            except Exception as e:
                log_event("sheet_extraction_error", {
                    "sheet": sheet_name,
                    "error": str(e)
                })
                continue
        
        if not all_data:
            raise ValueError("No data extracted from any sheets")
        
        log_event("extraction_completed", {
            "file_path": str(file_path),
            "total_rows": len(all_data),
            "sheets_processed": len(excel_file.sheet_names),
            "sample_columns": list(all_data[0].keys()) if all_data else []
        })
        
        return all_data
        
    except Exception as e:
        log_event("extraction_failed", {
            "file_path": str(file_path) if 'file_path' in locals() else "unknown",
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise

def extract_from_csv(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract data from CSV files as backup/alternative method.
    """
    try:
        df = pd.read_csv(file_path, dtype=str, na_filter=False)
        
        # Clean column names
        df.columns = [str(col).strip().replace('\n', ' ').replace('\r', ' ') for col in df.columns]
        
        # Convert to list of dictionaries
        data = []
        for idx, row in df.iterrows():
            row_dict = {}
            for col in df.columns:
                value = row[col]
                if pd.isna(value) or value == '':
                    row_dict[col] = None
                else:
                    cleaned_value = str(value).strip()
                    row_dict[col] = cleaned_value if cleaned_value else None
            
            if any(v is not None for v in row_dict.values()):
                row_dict['_sheet_name'] = 'Sheet1'
                row_dict['_row_index'] = idx + 2
                data.append(row_dict)
        
        log_event("csv_extraction_completed", {
            "file_path": file_path,
            "rows": len(data),
            "columns": list(df.columns)
        })
        
        return data
        
    except Exception as e:
        log_event("csv_extraction_failed", {
            "file_path": file_path,
            "error": str(e)
        })
        raise

# Main extraction function that handles both Excel and CSV
def extract_data_auto(file_path: str) -> List[Dict[str, Any]]:
    """
    Auto-detect file type and extract data accordingly.
    """
    file_path = Path(file_path)
    extension = file_path.suffix.lower()
    
    if extension == '.csv':
        return extract_from_csv(str(file_path))
    elif extension in ['.xlsx', '.xls']:
        return extract_data(str(file_path))
    else:
        raise ValueError(f"Unsupported file type: {extension}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extraction.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    try:
        data = extract_data_auto(file_path)
        print(f"Extracted {len(data)} rows")
        if data:
            print("Sample columns:", list(data[0].keys())[:10])
            print("First row sample:", {k: v for k, v in list(data[0].items())[:5]})
    except Exception as e:
        print(f"Extraction failed: {e}")
        sys.exit(1)
