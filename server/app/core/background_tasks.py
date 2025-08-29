"""
Background task processing
Handles heavy file processing operations asynchronously
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from logging_config import setup_logger, log_with_context
from pipeline_processor import FinancialDataProcessor

logger = setup_logger('background-tasks')
processor = FinancialDataProcessor()


async def process_file_async(file_path: str, company_id: int, filename: str) -> Dict[str, Any]:
    """
    Process uploaded file asynchronously
    Runs the complete financial data pipeline in background
    """
    
    try:
        log_with_context(logger, 'info', 'Starting background file processing', 
            file_path=file_path,
            company_id=company_id,
            filename=filename
        )
        
        processing_steps = []
        start_time = datetime.now()
        
        # Step 1: Data Ingestion
        ingest_result = processor.ingest_file(file_path, company_id)
        if not ingest_result.success:
            raise Exception(f"Ingestion failed: {ingest_result.message}")
        processing_steps.append("✓ Data ingested and persisted to database")
        
        # Step 2: Calculate Metrics
        metrics_result = processor.calculate_metrics(company_id)
        if not metrics_result.success:
            raise Exception(f"Metrics calculation failed: {metrics_result.message}")
        processing_steps.append("✓ Financial metrics calculated")
        
        # Step 3: Generate Questions
        questions_result = processor.generate_questions(company_id)
        if not questions_result.success:
            raise Exception(f"Question generation failed: {questions_result.message}")
        processing_steps.append("✓ Analytical questions generated")
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        log_with_context(logger, 'info', 'Background file processing completed', 
            company_id=company_id,
            file_path=file_path,
            processing_time=processing_time,
            steps=len(processing_steps)
        )
        
        return {
            "success": True,
            "message": "File processed successfully",
            "company_id": company_id,
            "processing_steps": processing_steps,
            "processing_time": processing_time
        }
        
    except Exception as e:
        log_with_context(logger, 'error', 'Background file processing failed', 
            error=str(e),
            company_id=company_id,
            file_path=file_path
        )
        
        # Clean up file on failure
        file_obj = Path(file_path)
        if file_obj.exists():
            file_obj.unlink()
        
        return {
            "success": False,
            "message": f"Processing failed: {str(e)}",
            "company_id": company_id,
            "error": str(e)
        }


async def generate_report_async(company_id: int, report_path: str) -> Dict[str, Any]:
    """
    Generate financial report asynchronously
    Creates PDF report in background for heavy operations
    """
    
    try:
        log_with_context(logger, 'info', 'Starting background report generation', 
            company_id=company_id,
            report_path=report_path
        )
        
        start_time = datetime.now()
        
        # Generate report using processor
        report_result = processor.generate_report(company_id, report_path)
        if not report_result.success:
            raise Exception(f"Report generation failed: {report_result.message}")
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Verify file was created
        report_file = Path(report_path)
        if not report_file.exists():
            raise Exception("Report file was not created successfully")
        
        log_with_context(logger, 'info', 'Background report generation completed', 
            company_id=company_id,
            report_path=report_path,
            processing_time=processing_time,
            file_size=report_file.stat().st_size
        )
        
        return {
            "success": True,
            "message": "Report generated successfully",
            "company_id": company_id,
            "report_path": report_path,
            "processing_time": processing_time,
            "file_size": report_file.stat().st_size
        }
        
    except Exception as e:
        log_with_context(logger, 'error', 'Background report generation failed', 
            error=str(e),
            company_id=company_id,
            report_path=report_path
        )
        
        return {
            "success": False,
            "message": f"Report generation failed: {str(e)}",
            "company_id": company_id,
            "error": str(e)
        }