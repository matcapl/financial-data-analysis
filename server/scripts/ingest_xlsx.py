# server/scripts/ingest_xlsx.py - Refactored to layered architecture orchestrator
import os
import sys
import yaml
from datetime import datetime

from utils import log_event, get_db_connection
from extraction import extract_data
from field_mapper import map_and_filter_row
from normalization import normalize_data  
from persistence import persist_data


class YAMLDrivenXLSXIngester:
    """
    Orchestrates the layered ingestion pipeline:
    Extract -> Map -> Normalize -> Persist
    Now fully YAML-driven using existing config/fields.yaml
    """
    
    def __init__(self, file_path: str, company_id: int = 1):
        self.file_path = file_path
        self.company_id = company_id
        self.results = {
            "file_path": file_path,
            "file_type": os.path.splitext(file_path)[1].lower(),
            "total_rows_processed": 0,
            "extracted_count": 0,
            "mapped_count": 0,
            "normalized_count": 0,
            "ingested_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "status": "started",
            "yaml_driven": True
        }
        
        # Load YAML configuration for header mapping
        self.header_synonyms = self._load_header_synonyms()
        
    def _load_header_synonyms(self) -> dict:
        """Load header synonym mapping from existing config/fields.yaml"""
        try:
            with open('config/fields.yaml', 'r') as f:
                config = yaml.safe_load(f)
                
            # Convert the existing fields structure to synonym mapping
            # Each field has 'synonyms' list that should map to the field name
            synonyms = {}
            for field_name, field_config in config['fields'].items():
                field_synonyms = field_config.get('synonyms', [])
                synonyms[field_name] = field_synonyms
                
            log_event("yaml_config_loaded", {
                "config_file": "config/fields.yaml",
                "field_count": len(synonyms),
                "synonym_count": sum(len(syns) for syns in synonyms.values())
            })
            
            return synonyms
            
        except Exception as e:
            log_event("yaml_config_error", {"error": str(e)})
            # Fallback to minimal synonyms if YAML fails
            return {
                "line_item": ["line_item", "lineitem", "item", "metric"],
                "period_label": ["period_label", "period", "date"],
                "value": ["value", "amount", "val"]
            }
            
    def _normalize_headers(self, raw_columns: list) -> dict:
        """
        Convert raw column headers to canonical names using YAML synonyms
        Replaces the hard-coded synonyms from original ingest_xlsx.py
        """
        
        canon_map = {}
        
        for raw_col in raw_columns:
            clean_col = raw_col.strip()
            lower_col = clean_col.lower()
            canonical_header = None
            
            # Find matching canonical header from YAML config
            for canonical_name, synonyms_list in self.header_synonyms.items():
                if lower_col in [s.lower() for s in synonyms_list]:
                    canonical_header = canonical_name
                    break
                    
            # Use canonical header if found, otherwise keep original (lowercased)
            canon_map[clean_col] = canonical_header if canonical_header else lower_col
            
        log_event("yaml_header_mapping_applied", {
            "original_headers": raw_columns,
            "mapped_headers": canon_map,
            "yaml_driven": True
        })
        
        return canon_map
        
    def process_file(self) -> dict:
        """Main orchestration method - coordinates all layers"""
        
        log_event("ingestion_started", {
            "file_path": self.file_path,
            "company_id": self.company_id,
            "yaml_driven": True
        })
        
        try:
            # Layer 1: Extract raw data from file
            raw_rows = extract_data(self.file_path)
            self.results["extracted_count"] = len(raw_rows)
            self.results["total_rows_processed"] = len(raw_rows)
            
            if not raw_rows:
                raise Exception("No data extracted from file")
                
            # Get column headers for normalization
            if raw_rows:
                raw_columns = list(raw_rows[0].keys())
                header_mapping = self._normalize_headers(raw_columns)
                
                # Apply header mapping to all rows
                for row in raw_rows:
                    # Create new dict with normalized headers
                    normalized_headers = {}
                    for old_key, value in row.items():
                        new_key = header_mapping.get(old_key, old_key)
                        normalized_headers[new_key] = value
                    # Update row in place
                    row.clear()
                    row.update(normalized_headers)
            
            log_event("file_processing_started", {
                "rows_found": len(raw_rows),
                "columns_found": list(raw_rows[0].keys()) if raw_rows else [],
                "file_path": self.file_path
            })
            
            # Layer 2: Map fields using existing field_mapper.py
            mapped_rows = []
            mapping_errors = 0
            
            for raw_row in raw_rows:
                try:
                    # Apply defaults (consistent with original ingest_xlsx.py)
                    defaults = {
                        "statement_type": None,
                        "category": None,
                        "value_type": raw_row.get("value_type") or "Actual",
                        "frequency": raw_row.get("frequency") or raw_row.get("period_type") or "Monthly",
                        "currency": raw_row.get("currency") or "USD"
                    }
                    for k, v in defaults.items():
                        raw_row.setdefault(k, v)
                        
                    # Use existing field mapper
                    mapped_row = map_and_filter_row(raw_row)
                    if mapped_row:
                        mapped_rows.append(mapped_row)
                    else:
                        mapping_errors += 1
                        
                except Exception as e:
                    mapping_errors += 1
                    log_event("field_mapping_error", {
                        "error": str(e),
                        "raw_row": raw_row
                    })
                    
            self.results["mapped_count"] = len(mapped_rows)
            self.results["error_count"] += mapping_errors
            
            # Layer 3: Normalize data for database insertion
            normalized_rows = normalize_data(mapped_rows, self.file_path)
            self.results["normalized_count"] = len(normalized_rows)
            
            # Layer 4: Persist to database
            persistence_results = persist_data(normalized_rows, self.company_id)
            
            # Update final results
            self.results.update({
                "ingested_count": persistence_results["inserted"],
                "skipped_count": persistence_results["skipped"],
                "status": "completed"
            })
            self.results["error_count"] += persistence_results["errors"]
            
            log_event("ingestion_completed", self.results)
            
            return self.results
            
        except Exception as e:
            self.results.update({
                "status": "failed",
                "error": str(e)
            })
            log_event("ingestion_failed", self.results)
            raise


# Backward compatibility - maintain existing interface
class XLSXIngester(YAMLDrivenXLSXIngester):
    """Legacy wrapper for backward compatibility"""
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # No cleanup needed in layered architecture


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_xlsx.py <file_path> [company_id]")
        sys.exit(1)

    file_path = sys.argv[1]
    company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"YAML-driven layered ingestion starting for file: {file_path}")
    
    try:
        ingester = YAMLDrivenXLSXIngester(file_path, company_id)
        result = ingester.process_file()
        print(f"Layered ingestion result: {result}")
        
        # Print summary
        if result["status"] == "completed":
            print(f"✅ Success: {result['ingested_count']} rows ingested, "
                  f"{result['skipped_count']} skipped, {result['error_count']} errors")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Ingestion failed: {e}")
        sys.exit(1)