#!/usr/bin/env python3
"""
Enhanced Excel/CSV Data Ingestion Module - CORRECTED THREE-LAYER VERSION

This module integrates with the three-layer ingestion pipeline:
- Uses extraction.py for data extraction
- Uses field_mapper.py for YAML-driven field mapping
- Uses normalization.py for period and value normalization
- Uses persistence.py for database persistence with deduplication

Author: Financial Data Analysis Team
Version: 3.0 (Three-Layer Integration)
"""

import pandas as pd
import numpy as np
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple, Any
import os
import sys

# Add server/scripts to path for imports
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

try:
    from extraction import extract_data
    from field_mapper import map_and_filter_row
    from normalization import normalize_data
    from persistence import persist_data
    from utils import log_event, get_db_connection
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all required modules are available in server/scripts/")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def read_csv_with_encoding_detection(file_path: Path) -> pd.DataFrame:
    """Read CSV file with automatic encoding detection"""
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            df = pd.read_csv(file_path, encoding=encoding, na_values=['', 'N/A', 'NA', 'null', 'NULL'])
            if not df.empty:
                logger.info(f"Successfully read CSV with {encoding} encoding")
                return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.warning(f"Error reading CSV with {encoding}: {e}")
            continue
    
    raise ValueError(f"Could not read CSV file with any encoding: {encodings}")

def read_excel_file(file_path: Path) -> Dict[str, pd.DataFrame]:
    """Read Excel file with comprehensive error handling"""
    logger.info(f"Reading Excel file: {file_path}")
    
    try:
        # Read all sheets
        excel_data = pd.read_excel(file_path, sheet_name=None, na_values=['', 'N/A', 'NA', 'null', 'NULL'])
        
        processed_sheets = {}
        for sheet_name, df in excel_data.items():
            if not df.empty:
                # Clean the dataframe
                df = df.dropna(how='all').dropna(axis=1, how='all')
                processed_sheets[sheet_name] = df
        
        return processed_sheets
    
    except Exception as e:
        logger.error(f"Failed to read Excel file: {e}")
        raise

def convert_dataframe_to_rows(df: pd.DataFrame, sheet_name: str = "Sheet1") -> List[Dict[str, Any]]:
    """Convert DataFrame to list of dictionaries for processing"""
    rows = []
    
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        row_dict = row.to_dict()
        row_dict['_row_number'] = idx
        row_dict['_sheet_name'] = sheet_name
        
        # Clean None values and convert to appropriate types
        cleaned_row = {}
        for key, value in row_dict.items():
            if pd.isna(value):
                cleaned_row[key] = None
            elif isinstance(value, (int, float, str)):
                cleaned_row[key] = value
            else:
                cleaned_row[key] = str(value)
        
        rows.append(cleaned_row)
    
    return rows

def ingest_file_three_layer(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Main three-layer ingestion orchestrator
    
    Flow: extraction → field_mapper → normalization → persistence
    """
    file_path = Path(file_path)
    results = {
        'success': False,
        'file_path': str(file_path),
        'stages_completed': [],
        'error_count': 0,
        'rows_processed': 0,
        'rows_persisted': 0,
        'errors': []
    }
    
    logger.info(f"Starting three-layer ingestion for: {file_path}")
    
    try:
        # STAGE 1: EXTRACTION
        logger.info(f"Stage 1: Extracting data from {file_path}")
        
        file_extension = file_path.suffix.lower()
        raw_data = []
        
        if file_extension in ['.xlsx', '.xls']:
            excel_sheets = read_excel_file(file_path)
            for sheet_name, df in excel_sheets.items():
                sheet_rows = convert_dataframe_to_rows(df, sheet_name)
                raw_data.extend(sheet_rows)
        
        elif file_extension == '.csv':
            df = read_csv_with_encoding_detection(file_path)
            raw_data = convert_dataframe_to_rows(df, "CSV")
        
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        results['stages_completed'].append('extraction')
        results['rows_extracted'] = len(raw_data)
        
        if not raw_data:
            raise ValueError("No data extracted from file")
        
        logger.info(f"✅ Extracted {len(raw_data)} rows")
        
        # STAGE 2: FIELD MAPPING
        logger.info(f"Stage 2: Field mapping for {len(raw_data)} rows")
        mapped_rows = []
        mapping_errors = 0
        
        for idx, row in enumerate(raw_data, 1):
            try:
                # Ensure row has required metadata
                if '_row_number' not in row:
                    row['_row_number'] = idx
                if 'source_file' not in row:
                    row['source_file'] = file_path.name
                
                mapped_row = map_and_filter_row(row)
                mapped_rows.append(mapped_row)
                
            except Exception as e:
                logger.warning(f"Row {idx} field mapping failed: {e}")
                results['errors'].append(f"Row {idx} mapping: {str(e)}")
                mapping_errors += 1
        
        results['stages_completed'].append('field_mapping')
        results['rows_mapped'] = len(mapped_rows)
        results['error_count'] += mapping_errors
        
        logger.info(f"✅ Mapped {len(mapped_rows)} rows ({mapping_errors} errors)")
        
        # STAGE 3: NORMALIZATION
        logger.info(f"Stage 3: Normalizing {len(mapped_rows)} rows")
        normalized_rows, norm_errors = normalize_data(mapped_rows, str(file_path))
        
        results['stages_completed'].append('normalization')
        results['rows_normalized'] = len(normalized_rows)
        results['error_count'] += norm_errors
        
        logger.info(f"✅ Normalized {len(normalized_rows)} rows ({norm_errors} errors)")
        
        # STAGE 4: PERSISTENCE
        logger.info(f"Stage 4: Persisting {len(normalized_rows)} rows")
        persistence_results = persist_data(normalized_rows)
        
        results['stages_completed'].append('persistence')
        results['rows_persisted'] = persistence_results['inserted']
        results['rows_skipped'] = persistence_results['skipped']
        results['error_count'] += persistence_results['errors']
        
        logger.info(f"✅ Persisted {persistence_results['inserted']} rows (skipped: {persistence_results['skipped']}, errors: {persistence_results['errors']})")
        
        # Mark as successful
        results['success'] = True
        results['rows_processed'] = len(raw_data)
        
        log_event("three_layer_ingestion_complete", {
            'file_path': str(file_path),
            'stages_completed': len(results['stages_completed']),
            'rows_extracted': results.get('rows_extracted', 0),
            'rows_persisted': results['rows_persisted'],
            'error_count': results['error_count']
        })
        
        logger.info(f"🎉 Three-layer ingestion completed successfully!")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Three-layer ingestion failed: {error_msg}")
        log_event("three_layer_ingestion_failed", {
            'file_path': str(file_path),
            'error': error_msg,
            'stages_completed': results['stages_completed']
        })
        results['error'] = error_msg
        results['errors'].append(f"Pipeline failure: {error_msg}")
    
    return results

def main():
    """Main entry point for command-line usage"""
    if len(sys.argv) < 2:
        print("Usage: python ingest_xlsx.py <file_path>")
        print("Example: python ingest_xlsx.py data/financial_data_template.csv")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # Validate file exists
    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    # Run three-layer ingestion
    result = ingest_file_three_layer(file_path)
    
    # Print results
    print(f"\n{'='*60}")
    print("THREE-LAYER INGESTION RESULTS")
    print(f"{'='*60}")
    print(f"File: {result['file_path']}")
    print(f"Success: {'✅' if result['success'] else '❌'}")
    print(f"Stages Completed: {' → '.join(result['stages_completed'])}")
    print(f"Rows Extracted: {result.get('rows_extracted', 0)}")
    print(f"Rows Mapped: {result.get('rows_mapped', 0)}")
    print(f"Rows Normalized: {result.get('rows_normalized', 0)}")
    print(f"Rows Persisted: {result['rows_persisted']}")
    print(f"Rows Skipped: {result.get('rows_skipped', 0)}")
    print(f"Total Errors: {result['error_count']}")
    
    if result.get('errors'):
        print(f"\nErrors:")
        for error in result['errors'][:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(result['errors']) > 5:
            print(f"  ... and {len(result['errors']) - 5} more errors")
    
    if result.get('error'):
        print(f"\nFatal Error: {result['error']}")
    
    print(f"{'='*60}")
    
    if result['success']:
        print(f"✅ Three-layer ingestion completed: {result['rows_persisted']} rows persisted")
        sys.exit(0)
    else:
        print(f"❌ Three-layer ingestion failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()