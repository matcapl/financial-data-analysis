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
from logging_config import setup_logger, log_with_context, log_pipeline_step

try:
    # Import all processing modules
    from extraction import extract_data
    from field_mapper import map_and_filter_row
    from normalization import normalize_data
    from persistence import persist_data
    from utils import log_event, get_db_connection
    
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
    
    def ingest_file(self, file_path: str, company_id: int) -> PipelineResult:
        """
        Process file through the three-layer ingestion pipeline
        Replaces: runPythonScript('ingest_xlsx.py', [file_path, company_id])
        """
        try:
            log_with_context(
                self.logger, 'info', 'Starting file ingestion',
                filePath=Path(file_path).name,
                companyId=company_id
            )
            
            # Stage 1: Extract data
            log_pipeline_step(self.logger, 'data_extraction', True, stage=1)
            extracted_data = extract_data(file_path)
            if not extracted_data:
                return PipelineResult(False, "No data extracted from file", errors=["Empty or invalid file"])
            
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
            
            for row in extracted_data:
                try:
                    mapped_row = map_and_filter_row(row)
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
            normalized_data, normalization_error_count = normalize_data(mapped_rows, file_path)
            
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
                    persisted_count = persist_data(period_rows, company_id, period_id)
                    total_persisted += persisted_count
                    
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
                        "rows_persisted": total_persisted
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
            result = subprocess.run([
                sys.executable, 
                str(current_dir / 'calc_metrics.py'), 
                str(company_id)
            ], capture_output=True, text=True)
            
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
            result = subprocess.run([
                sys.executable,
                str(current_dir / 'questions_engine.py'),
                str(company_id)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return PipelineResult(True, "Questions generated successfully", data={"output": result.stdout})
            else:
                return PipelineResult(False, "Question generation failed", errors=[result.stderr])
                    
        except Exception as e:
            error_msg = f"Question generation failed: {str(e)}"
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
                result = subprocess.run([
                    sys.executable,
                    str(current_dir / 'report_generator.py'),
                    str(company_id),
                    output_path
                ], capture_output=True, text=True)
                
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
        print("Operations: ingest_file, calculate_metrics, generate_questions, generate_report")
        sys.exit(1)
    
    processor = FinancialDataProcessor()
    operation = sys.argv[1]
    
    try:
        if operation == "ingest_file" and len(sys.argv) >= 4:
            file_path = sys.argv[2]
            company_id = int(sys.argv[3])
            result = processor.ingest_file(file_path, company_id)
        
        elif operation == "calculate_metrics" and len(sys.argv) >= 3:
            company_id = int(sys.argv[2])
            result = processor.calculate_metrics(company_id)
        
        elif operation == "generate_questions" and len(sys.argv) >= 3:
            company_id = int(sys.argv[2])
            result = processor.generate_questions(company_id)
        
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