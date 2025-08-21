# server/scripts/ingest_xlsx.py - FIXED VERSION with enhanced error handling and robustness
import os
import sys
import yaml
from datetime import datetime
from utils import log_event, get_db_connection
from extraction import extract_data
from field_mapper import map_and_filter_row
from normalization import normalize_data 
from persistence import persist_data

class RobustYAMLDrivenXLSXIngester:
    """
    FIXED: Enhanced orchestrator for the layered ingestion pipeline with:
    - Better error handling and recovery
    - Period creation validation
    - Detailed diagnostic logging
    - Graceful degradation on partial failures
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
            "yaml_driven": True,
            "diagnostics": {
                "periods_created": 0,
                "line_items_found": 0,
                "unique_periods": set(),
                "unique_line_items": set()
            }
        }

        # Load YAML configuration for header mapping
        self.header_synonyms = self._load_header_synonyms()

    def _load_header_synonyms(self) -> dict:
        """FIXED: Load header synonym mapping from existing config/fields.yaml with fallback"""
        try:
            with open('config/fields.yaml', 'r') as f:
                config = yaml.safe_load(f)

            # Convert the existing fields structure to synonym mapping
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
        """Convert raw column headers to canonical names using YAML synonyms"""

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

    def _validate_pipeline_prerequisites(self):
        """
        ENHANCED: Pre-flight checks to ensure database and config are ready
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Check essential tables exist
                    cur.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name IN ('companies', 'periods', 'line_item_definitions', 'financial_metrics')
                    """)
                    tables = [row[0] for row in cur.fetchall()]

                    if len(tables) < 4:
                        raise Exception(f"Missing required tables. Found: {tables}")

                    # Check line_item_definitions are seeded
                    cur.execute("SELECT COUNT(*) FROM line_item_definitions")
                    line_item_count = cur.fetchone()[0]

                    if line_item_count == 0:
                        log_event("seeding_line_items", {"message": "No line items found, seeding from YAML"})
                        from utils import seed_line_item_definitions
                        seed_line_item_definitions()

                    # Get available line items for diagnostics
                    cur.execute("SELECT name FROM line_item_definitions")
                    available_line_items = [row[0] for row in cur.fetchall()]

                    self.results["diagnostics"]["line_items_found"] = len(available_line_items)

                    log_event("prerequisites_validated", {
                        "tables_found": tables,
                        "line_items_available": available_line_items
                    })

        except Exception as e:
            log_event("prerequisites_failed", {"error": str(e)})
            raise Exception(f"Pipeline prerequisites not met: {e}")

    def _post_ingestion_diagnostics(self):
        """
        ENHANCED: Run diagnostics after ingestion to understand what was created
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Check periods created
                    cur.execute("""
                        SELECT DISTINCT period_label, period_type 
                        FROM periods 
                        ORDER BY period_label
                    """)
                    periods = cur.fetchall()

                    # Check financial metrics created
                    cur.execute("""
                        SELECT COUNT(*) as metric_count,
                               COUNT(DISTINCT period_id) as unique_periods,
                               COUNT(DISTINCT line_item_id) as unique_line_items
                        FROM financial_metrics 
                        WHERE company_id = %s
                    """, (self.company_id,))

                    metrics_stats = cur.fetchone()

                    # Sample of what was inserted
                    cur.execute("""
                        SELECT 
                            li.name as line_item,
                            p.period_label,
                            fm.value_type,
                            fm.value
                        FROM financial_metrics fm
                        JOIN line_item_definitions li ON fm.line_item_id = li.id
                        JOIN periods p ON fm.period_id = p.id
                        WHERE fm.company_id = %s
                        ORDER BY fm.created_at DESC
                        LIMIT 5
                    """, (self.company_id,))

                    sample_metrics = cur.fetchall()

                    # Update diagnostics
                    self.results["diagnostics"].update({
                        "periods_in_db": len(periods),
                        "periods_created": periods,
                        "metrics_count": metrics_stats[0] if metrics_stats else 0,
                        "unique_periods_used": metrics_stats[1] if metrics_stats else 0,
                        "unique_line_items_used": metrics_stats[2] if metrics_stats else 0,
                        "sample_inserted_data": sample_metrics
                    })

                    log_event("post_ingestion_diagnostics", self.results["diagnostics"])

        except Exception as e:
            log_event("diagnostics_error", {"error": str(e)})

    def process_file(self) -> dict:
        """
        ENHANCED: Main orchestration method with better error handling and diagnostics
        """

        log_event("ingestion_started", {
            "file_path": self.file_path,
            "company_id": self.company_id,
            "yaml_driven": True
        })

        try:
            # Pre-flight validation
            self._validate_pipeline_prerequisites()

            # Layer 1: Extract raw data from file
            raw_rows = extract_data(self.file_path)
            self.results["extracted_count"] = len(raw_rows)
            self.results["total_rows_processed"] = len(raw_rows)

            if not raw_rows:
                raise Exception("No data extracted from file")

            log_event("extraction_sample", {
                "first_row_keys": list(raw_rows[0].keys()) if raw_rows else [],
                "first_row_sample": {k: v for k, v in list(raw_rows[0].items())[:5]} if raw_rows else {}
            })

            # Apply header normalization using YAML
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
                    "columns_after_header_mapping": list(raw_rows[0].keys()) if raw_rows else [],
                    "file_path": self.file_path
                })

            # Layer 2: Map fields using existing field_mapper.py
            mapped_rows = []
            mapping_errors = 0

            for i, raw_row in enumerate(raw_rows):
                try:
                    # Ensure row tracking
                    raw_row['_row_number'] = i + 1

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
                        # Preserve row number through mapping
                        mapped_row['_row_number'] = i + 1
                        mapped_rows.append(mapped_row)

                        # Track unique values for diagnostics
                        if mapped_row.get("line_item"):
                            self.results["diagnostics"]["unique_line_items"].add(mapped_row["line_item"])
                        if mapped_row.get("period_label"):
                            self.results["diagnostics"]["unique_periods"].add(mapped_row["period_label"])
                    else:
                        mapping_errors += 1
                        log_event("field_mapping_null_result", {
                            "row_number": i + 1,
                            "raw_row_sample": {k: v for k, v in raw_row.items() if k in ['line_item', 'period_label', 'value']}
                        })

                except Exception as e:
                    mapping_errors += 1
                    log_event("field_mapping_error", {
                        "row_number": i + 1,
                        "error": str(e),
                        "raw_row_sample": {k: v for k, v in raw_row.items() if k in ['line_item', 'period_label', 'value']}
                    })

            self.results["mapped_count"] = len(mapped_rows)
            self.results["error_count"] += mapping_errors

            log_event("mapping_completed", {
                "mapped_count": len(mapped_rows),
                "mapping_errors": mapping_errors,
                "unique_line_items": list(self.results["diagnostics"]["unique_line_items"]),
                "unique_periods": list(self.results["diagnostics"]["unique_periods"])
            })

            # Layer 3: Normalize data for database insertion - FIXED
            if mapped_rows:
                normalized_rows, normalization_errors = normalize_data(mapped_rows, self.file_path)
                self.results["normalized_count"] = len(normalized_rows)
                self.results["error_count"] += normalization_errors

                log_event("normalization_completed", {
                    "normalized_count": len(normalized_rows),
                    "normalization_errors": normalization_errors,
                    "first_normalized_row": normalized_rows[0] if normalized_rows else {}
                })
            else:
                log_event("no_mapped_data", {"message": "No data survived field mapping layer"})
                normalized_rows = []
                normalization_errors = 0

            # Layer 4: Persist to database
            if normalized_rows:
                persistence_results = persist_data(normalized_rows, self.company_id)

                # Update final results
                self.results.update({
                    "ingested_count": persistence_results["inserted"],
                    "skipped_count": persistence_results["skipped"],
                    "status": "completed"
                })
                self.results["error_count"] += persistence_results["errors"]

                # Run post-ingestion diagnostics
                self._post_ingestion_diagnostics()

            else:
                log_event("no_data_to_persist", {
                    "message": "No normalized rows to persist",
                    "normalization_errors": normalization_errors,
                    "mapping_errors": mapping_errors
                })
                self.results["status"] = "completed_no_data"

            log_event("ingestion_completed", self.results)

            return self.results

        except Exception as e:
            self.results.update({
                "status": "failed",
                "error": str(e)
            })
            log_event("ingestion_failed", self.results)
            raise

    def print_detailed_summary(self):
        """
        ENHANCED: Print comprehensive summary of ingestion results
        """
        print(f"\n{'='*60}")
        print(f"INGESTION SUMMARY: {self.file_path}")
        print(f"{'='*60}")

        # Pipeline flow summary
        print(f"📊 Pipeline Flow:")
        print(f"   {self.results['extracted_count']} extracted → {self.results['mapped_count']} mapped → {self.results['normalized_count']} normalized → {self.results['ingested_count']} ingested")

        # Error summary  
        if self.results["error_count"] > 0:
            print(f"⚠️  Errors: {self.results['error_count']} total")

        # Success metrics
        print(f"✅ Success: {self.results['ingested_count']} rows ingested, {self.results['skipped_count']} skipped")

        # Diagnostics
        diag = self.results["diagnostics"]
        if diag.get("unique_line_items"):
            print(f"📈 Line Items: {list(diag['unique_line_items'])}")
        if diag.get("unique_periods"):
            print(f"📅 Periods: {list(diag['unique_periods'])}")
        if diag.get("periods_created"):
            print(f"🗓️  Periods Created: {diag['periods_created']}")

        # Sample data
        if diag.get("sample_inserted_data"):
            print(f"\n💾 Sample Inserted Data:")
            for i, row in enumerate(diag["sample_inserted_data"][:3], 1):
                print(f"   {i}. {row[0]} | {row[1]} | {row[2]} | {row[3]}")

        print(f"{'='*60}")

# Backward compatibility - maintain existing interface
class XLSXIngester(RobustYAMLDrivenXLSXIngester):
    """Legacy wrapper for backward compatibility"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# Command-line interface with enhanced error reporting
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_xlsx.py <file_path> [company_id]")
        sys.exit(1)

    file_path = sys.argv[1]
    company_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)

    print(f"🚀 ENHANCED YAML-driven layered ingestion starting for file: {file_path}")
    print(f"🏢 Company ID: {company_id}")

    try:
        ingester = RobustYAMLDrivenXLSXIngester(file_path, company_id)
        result = ingester.process_file()

        # Print detailed summary
        ingester.print_detailed_summary()

        # Final status
        if result["status"] == "completed":
            if result["ingested_count"] > 0:
                print(f"\n🎉 SUCCESS: Pipeline completed successfully!")
                print(f"   📊 {result['ingested_count']} rows ingested with {result['error_count']} errors")
            else:
                print(f"\n⚠️  WARNING: Pipeline completed but no data was ingested!")
                print(f"   🔍 Check logs/events.json for detailed error analysis")
                sys.exit(1)
        else:
            print(f"\n❌ FAILED: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        print(f"\n💥 CRITICAL FAILURE: {e}")
        print(f"🔍 Check logs/events.json for detailed error analysis")
        sys.exit(1)
