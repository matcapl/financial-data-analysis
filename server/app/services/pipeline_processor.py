#!/usr/bin/env python3
"""
Unified Financial Data Processing Pipeline
Replaces subprocess calls with direct Python function imports for better performance and error handling.
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import traceback

# Add current directory to Python path
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

# Import structured logging
from app.utils.logging_config import setup_logger, log_with_context, log_pipeline_step

try:
    # Import all processing modules
    from extraction import extract_data
    from field_mapper import map_and_filter_row
    from normalization import normalize_data
    from persistence import persist_data
    from app.utils.utils import log_event, get_db_connection
    from app.services.company_identity import resolve_company_id_for_upload
    from ingest_pdf import ingest_pdf
    
    # Import specific script functions (we'll refactor these)
    import ingest_xlsx
    import calc_metrics
    import questions_engine
    import report_generator
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}")
    sys.exit(1)

# Configure structured logging
logger = setup_logger('pipeline-processor')

class PipelineResult:
    """Result object for pipeline operations"""
    def __init__(self, success: bool = True, message: str = "", data: Any = None, errors: list = None):
        self.success = success
        self.message = message
        self.data = data
        self.errors = errors or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "errors": self.errors
        }

class FinancialDataProcessor:
    """Main processor class for financial data pipeline operations"""
    
    def __init__(self):
        self.logger = setup_logger('financial-data-processor')
    
    def ingest_file(self, file_path: str, company_id: int, document_id: int = None) -> PipelineResult:
        """Process file through the three-layer ingestion pipeline.

        Canonical entrypoints should provide a `document_id` (e.g. API upload).
        For robustness (CLI runs, background tasks), if `document_id` is missing,
        we create a `documents` row automatically so provenance and reconciliation
        remain functional.
        """
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return PipelineResult(False, f"File not found: {file_path}")

            file_extension = file_path_obj.suffix.lower()

            if document_id is None:
                try:
                    with get_db_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1 FROM companies WHERE id = %s", (company_id,))
                            if cur.fetchone() is None:
                                cur.execute(
                                    "INSERT INTO companies (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                                    (company_id, f"Company {company_id}"),
                                )
                                conn.commit()

                            company_id = resolve_company_id_for_upload(conn, company_id=company_id, filename=file_path_obj.name)

                            cur.execute(
                                "INSERT INTO documents (company_id, original_filename, stored_path) VALUES (%s, %s, %s) RETURNING id",
                                (company_id, file_path_obj.name, str(file_path_obj.resolve())), 
                            )
                            document_id = cur.fetchone()[0]
                            conn.commit()
                except Exception as e:
                    return PipelineResult(False, f"Failed to create document provenance: {e}")

            log_with_context(
                self.logger, 'info', 'Starting file ingestion',
                filePath=file_path_obj.name,
                companyId=company_id,
                documentId=document_id,
                fileExtension=file_extension
            )
            
            # Route PDF files to dedicated PDF ingestion service
            if file_extension == '.pdf':
                log_with_context(
                    self.logger, 'info', 'Processing PDF file with dedicated PDF ingestion service',
                    filePath=file_path_obj.name
                )
                
                pdf_result = ingest_pdf(file_path, company_id, document_id=document_id)
                
                # Check if PDF ingestion was successful
                if pdf_result.get('status') == 'no_data':
                    return PipelineResult(False, "No data extracted from PDF file", errors=["Empty or invalid PDF file"])
                
                ingested_count = pdf_result.get('persisted', pdf_result.get('ingested', 0))
                error_count = pdf_result.get('persist_errors', pdf_result.get('errors', 0))
                
                skipped = int(pdf_result.get('skipped', 0) or 0)
                normalized_rows = int(pdf_result.get('rows_normalized', 0) or 0)

                if ingested_count > 0:
                    return PipelineResult(
                        success=True,
                        message=f"Successfully processed {ingested_count} rows from PDF",
                        data={
                            "rows_extracted": pdf_result.get('rows_extracted', 0),
                            "rows_mapped": pdf_result.get('rows_mapped', 0),
                            "rows_normalized": normalized_rows,
                            "rows_persisted": ingested_count,
                            "rows_skipped": skipped,
                            "pdf_processing_errors": error_count,
                        },
                    )

                # Treat dedupe-only runs as success (we still extracted and matched facts)
                if normalized_rows > 0 and skipped > 0:
                    return PipelineResult(
                        success=True,
                        message=f"Processed PDF (deduped): skipped {skipped}",
                        data={
                            "rows_extracted": pdf_result.get('rows_extracted', 0),
                            "rows_mapped": pdf_result.get('rows_mapped', 0),
                            "rows_normalized": normalized_rows,
                            "rows_persisted": 0,
                            "rows_skipped": skipped,
                            "pdf_processing_errors": error_count,
                        },
                    )

                return PipelineResult(
                    False,
                    "PDF processing failed - no data persisted",
                    errors=[f"PDF ingestion returned: {pdf_result}"],
                )
            
            # Standard pipeline for Excel/CSV files
            # Stage 1: Extract data
            log_pipeline_step(self.logger, 'data_extraction', True, stage=1)
            extracted_data = extract_data(file_path)
            if not extracted_data:
                return PipelineResult(False, "No data extracted from file", errors=["Empty or invalid file"])

            # Optional: per-company XLSX sheet filtering (avoid IRR models, etc.)
            try:
                from field_mapper import COMPANY_OVERRIDES

                ch = None
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute('SELECT companies_house_number FROM companies WHERE id=%s', (company_id,))
                        r = cur.fetchone()
                        ch = r[0] if r else None

                xcfg = (COMPANY_OVERRIDES or {}).get('xlsx', {}).get(str(ch), {}) if ch else {}
                deny = [s.lower() for s in (xcfg.get('deny') or []) if isinstance(s, str)]
                allow = [s.lower() for s in (xcfg.get('allow') or []) if isinstance(s, str)]

                if deny or allow:
                    def sheet_ok(sheet: str) -> bool:
                        s = (sheet or '').lower()
                        if allow and not any(p in s for p in allow):
                            return False
                        if deny and any(p in s for p in deny):
                            return False
                        return True

                    before = len(extracted_data)
                    extracted_data = [r for r in extracted_data if sheet_ok(r.get('_sheet_name'))]
                    log_with_context(
                        self.logger,
                        'info',
                        'XLSX sheet filter applied',
                        rowsBefore=before,
                        rowsAfter=len(extracted_data),
                        allow=allow,
                        deny=deny,
                    )
            except Exception:
                pass
            
            rows_extracted = len(extracted_data)
            log_with_context(
                self.logger, 'info', 'Data extraction completed',
                rowsExtracted=rows_extracted,
                stage=1
            )
            
            # Stage 2: Field mapping
            log_pipeline_step(self.logger, 'field_mapping', True, stage=2)
            mapped_rows = []
            mapping_errors = []

            companies_house_number = None
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute('SELECT companies_house_number FROM companies WHERE id=%s', (company_id,))
                        r = cur.fetchone()
                        companies_house_number = r[0] if r else None
            except Exception:
                companies_house_number = None

            for row in extracted_data:
                try:
                    mapped_row = map_and_filter_row({**row, "companies_house_number": companies_house_number})
                    if mapped_row:
                        mapped_rows.append(mapped_row)
                except Exception as e:
                    mapping_errors.append(f"Row mapping error: {str(e)}")
            
            log_with_context(
                self.logger, 'info', 'Field mapping completed',
                rowsMapped=len(mapped_rows),
                mappingErrors=len(mapping_errors),
                stage=2
            )
            
            # Stage 3: Normalization
            log_pipeline_step(self.logger, 'data_normalization', True, stage=3)
            normalized_data, normalization_error_count, rejected = normalize_data(mapped_rows, file_path, company_id, document_id)

            # Best-effort persistence of rejected candidates for audit.
            if rejected:
                try:
                    from rejections_persistence import persist_fact_rejections

                    persist_fact_rejections(rejected, company_id=company_id, document_id=document_id)
                except Exception:
                    pass
            
            log_with_context(
                self.logger, 'info', 'Data normalization completed',
                rowsNormalized=len(normalized_data),
                normalizationErrors=normalization_error_count,
                stage=3
            )
            
            # Stage 4: Persistence
            if normalized_data:
                log_pipeline_step(self.logger, 'database_persistence', True, stage=4)
                
                # Group rows by period_id since persist_data expects single period
                from collections import defaultdict
                grouped_by_period = defaultdict(list)
                for row in normalized_data:
                    period_id = row['period_id']
                    grouped_by_period[period_id].append(row)
                
                total_persisted = 0
                for period_id, period_rows in grouped_by_period.items():
                    persist_result = persist_data(period_rows, company_id, period_id)
                    total_persisted += persist_result.get('inserted', 0)
                    
                log_with_context(
                    self.logger, 'info', 'Database persistence completed',
                    rowsPersisted=total_persisted,
                    periodsProcessed=len(grouped_by_period),
                    stage=4
                )
                
                return PipelineResult(
                    success=True,
                    message=f"Successfully processed {total_persisted} rows",
                    data={
                        "rows_extracted": rows_extracted,
                        "rows_mapped": len(mapped_rows),
                        "rows_normalized": len(normalized_data),
                        "rows_persisted": total_persisted,
                        "rows_rejected": len(rejected),
                    },
                    errors=mapping_errors + [f"{normalization_error_count} normalization errors"]
                )
            else:
                return PipelineResult(
                    False, 
                    "No data to persist after normalization",
                    errors=mapping_errors + [f"{normalization_error_count} normalization errors"]
                )
                
        except Exception as e:
            error_msg = f"Pipeline failed: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            return PipelineResult(False, error_msg, errors=[str(e)])
    
    def calculate_metrics(self, company_id: int) -> PipelineResult:
        """
        Calculate derived metrics for a company
        Replaces: runPythonScript('calc_metrics.py', [company_id])
        """
        try:
            self.logger.info(f"Calculating metrics for company {company_id}")
            
            # Use subprocess to call the script with command line arguments
            import subprocess
            # Get project root directory  
            project_root = current_dir.parent.parent.parent
            result = subprocess.run([
                sys.executable, 
                str(current_dir / 'calc_metrics.py'), 
                str(company_id)
            ], capture_output=True, text=True, cwd=str(project_root))
            
            if result.returncode == 0:
                return PipelineResult(True, "Metrics calculated successfully", data={"output": result.stdout})
            else:
                return PipelineResult(False, "Metrics calculation failed", errors=[result.stderr])
                    
        except Exception as e:
            error_msg = f"Metrics calculation failed: {str(e)}"
            self.logger.error(error_msg)
            return PipelineResult(False, error_msg, errors=[str(e)])
    
    def generate_questions(self, company_id: int) -> PipelineResult:
        """
        Generate analytical questions for a company
        Replaces: runPythonScript('questions_engine.py', [company_id])
        """
        try:
            self.logger.info(f"Generating questions for company {company_id}")
            
            # Use subprocess to call the script with command line arguments
            import subprocess
            # Get project root directory  
            project_root = current_dir.parent.parent.parent
            result = subprocess.run([
                sys.executable,
                str(current_dir / 'questions_engine.py'),
                str(company_id)
            ], capture_output=True, text=True, cwd=str(project_root))
            
            if result.returncode == 0:
                return PipelineResult(True, "Questions generated successfully", data={"output": result.stdout})
            else:
                return PipelineResult(False, "Question generation failed", errors=[result.stderr])
                    
        except Exception as e:
            error_msg = f"Question generation failed: {str(e)}"
            self.logger.error(error_msg)
            return PipelineResult(False, error_msg, errors=[str(e)])
    
    def generate_findings(self, company_id: int) -> PipelineResult:
        """Generate deterministic findings for board-pack prioritisation."""
        try:
            self.logger.info(f"Generating findings for company {company_id}")

            import subprocess
            project_root = current_dir.parent.parent.parent
            result = subprocess.run(
                [
                    sys.executable,
                    str(current_dir / 'findings_engine.py'),
                    str(company_id),
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )

            if result.returncode == 0:
                return PipelineResult(True, "Findings generated successfully", data={"output": result.stdout})
            else:
                return PipelineResult(False, "Findings generation failed", errors=[result.stderr])

        except Exception as e:
            error_msg = f"Findings generation failed: {str(e)}"
            self.logger.error(error_msg)
            return PipelineResult(False, error_msg, errors=[str(e)])

    def generate_report(self, company_id: int, output_path: str) -> PipelineResult:
        """
        Generate PDF report for a company
        Replaces: runPythonScript('report_generator.py', [company_id, output_path])
        """
        try:
            self.logger.info(f"Generating report for company {company_id}")
            
            if hasattr(report_generator, 'main'):
                result = report_generator.main(company_id, output_path)
                return PipelineResult(True, f"Report generated: {output_path}", data={"output_path": output_path})
            else:
                # Fallback to subprocess
                import subprocess
                # Get project root directory  
                project_root = current_dir.parent.parent.parent
                result = subprocess.run([
                    sys.executable,
                    str(current_dir / 'report_generator.py'),
                    str(company_id),
                    output_path
                ], capture_output=True, text=True, cwd=str(project_root))
                
                if result.returncode == 0:
                    return PipelineResult(True, f"Report generated: {output_path}", data={"output_path": output_path})
                else:
                    return PipelineResult(False, "Report generation failed", errors=[result.stderr])
                    
        except Exception as e:
            error_msg = f"Report generation failed: {str(e)}"
            self.logger.error(error_msg)
            return PipelineResult(False, error_msg, errors=[str(e)])

def main():
    """CLI interface for the pipeline processor"""
    if len(sys.argv) < 2:
        print("Usage: python pipeline_processor.py <operation> [args...]")
        print("Operations: ingest_file, calculate_metrics, generate_questions, generate_findings, generate_report")
        sys.exit(1)
    
    processor = FinancialDataProcessor()
    operation = sys.argv[1]
    
    try:
        if operation == "ingest_file" and len(sys.argv) >= 4:
            file_path = sys.argv[2]
            company_id = int(sys.argv[3])
            result = processor.ingest_file(file_path, company_id, document_id=None)
        
        elif operation == "calculate_metrics" and len(sys.argv) >= 3:
            company_id = int(sys.argv[2])
            result = processor.calculate_metrics(company_id)
        
        elif operation == "generate_questions" and len(sys.argv) >= 3:
            company_id = int(sys.argv[2])
            result = processor.generate_questions(company_id)

        elif operation == "generate_findings" and len(sys.argv) >= 3:
            company_id = int(sys.argv[2])
            result = processor.generate_findings(company_id)
        
        elif operation == "generate_report" and len(sys.argv) >= 4:
            company_id = int(sys.argv[2])
            output_path = sys.argv[3]
            result = processor.generate_report(company_id, output_path)
        
        else:
            print(f"Invalid operation or missing arguments: {operation}")
            sys.exit(1)
        
        # Output result as JSON
        print(json.dumps(result.to_dict(), indent=2))
        
        # Exit with appropriate code
        sys.exit(0 if result.success else 1)
        
    except Exception as e:
        error_result = PipelineResult(False, f"Operation failed: {str(e)}", errors=[str(e)])
        print(json.dumps(error_result.to_dict(), indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()