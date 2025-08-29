# server/scripts/extraction.py
import pandas as pd
import openpyxl
import sys
from pathlib import Path
from typing import List, Dict, Any

# Path insert not needed, utils is in same directory
from utils import log_event

def extract_data(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract data from Excel files (.xlsx, .xls) and CSV files (.csv) and return as list of dictionaries.
    Handles multiple sheets, merged cells, and various data formats.
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        extension = file_path.suffix.lower()
        if extension not in ['.xlsx', '.xls', '.csv']:
            raise ValueError(f"Unsupported file type: {extension}")
        
        log_event("extraction_started", {
            "file_path": str(file_path),
            "file_size": file_path.stat().st_size,
            "file_type": extension
        })
        
        all_data = []
        
        if extension == '.csv':
            # Handle CSV files
            try:
                # Read CSV with multiple encoding attempts
                encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                df = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(
                            file_path,
                            encoding=encoding,
                            dtype=str,  # Read everything as string initially
                            na_filter=False,  # Don't convert empty cells to NaN
                            keep_default_na=False
                        )
                        break
                    except UnicodeDecodeError:
                        continue
                
                if df is None:
                    raise ValueError("Unable to read CSV file with any supported encoding")
                
                if not df.empty:
                    # Clean column names
                    df.columns = [str(col).strip().replace('\n', ' ').replace('\r', ' ') for col in df.columns]
                    
                    # Convert to list of dictionaries
                    for idx, row in df.iterrows():
                        row_dict = {}
                        for col in df.columns:
                            value = row[col]
                            # Clean and normalize cell values
                            if pd.isna(value) or value == '':
                                row_dict[col] = None
                            else:
                                row_dict[col] = str(value).strip()
                        
                        # Skip completely empty rows
                        if any(v is not None and v != '' for v in row_dict.values()):
                            row_dict['_source_sheet'] = 'CSV'
                            all_data.append(row_dict)
                
                log_event("csv_processed", {"rows_extracted": len(all_data)})
                
            except Exception as e:
                log_event("csv_error", {"error": str(e)})
                raise ValueError(f"Failed to process CSV file: {str(e)}")
        
        else:
            # Handle Excel files
            excel_file = pd.ExcelFile(file_path, engine='openpyxl' if extension == '.xlsx' else 'xlrd')
            
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
            raise ValueError("No data extracted from file")
        
        log_event("extraction_completed", {
            "file_path": str(file_path),
            "total_rows": len(all_data),
            "file_type": extension
        })
        
        return all_data
        
    except Exception as e:
        log_event("extraction_failed", {
            "file_path": str(file_path) if 'file_path' in locals() else 'unknown',
            "error": str(e)
        })
        raise