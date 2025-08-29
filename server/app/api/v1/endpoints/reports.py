"""
Reports endpoint for report generation and listing
Handles report generation and file serving
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils import get_db_connection
from logging_config import setup_logger, log_with_context
from pipeline_processor import FinancialDataProcessor
from app.models.api.requests import ReportRequest
from app.models.api.responses import ReportResponse
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["reports"])
logger = setup_logger('financial-data-api')
processor = FinancialDataProcessor()

REPORTS_DIR = settings.project_root / "reports"

@router.get("/reports")
async def list_reports():
    """List all generated PDF reports"""
    try:
        reports = []
        if REPORTS_DIR.exists():
            for file_path in REPORTS_DIR.glob("*.pdf"):
                stat = file_path.stat()
                reports.append({
                    "id": file_path.name,
                    "filename": file_path.name,
                    "url": f"/reports/{file_path.name}",
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size
                })
        
        # Sort by creation time (most recent first)
        reports.sort(key=lambda x: x["created"], reverse=True)
        return reports
        
    except Exception as e:
        log_with_context(logger, 'error', 'Failed to list reports', error=str(e))
        return []

@router.get("/data-files")
async def list_data_files():
    """List uploaded data files for debugging/testing"""
    try:
        files = []
        data_dir = settings.project_root / "data"
        for file_path in data_dir.glob("*"):
            if file_path.suffix.lower() in ['.csv', '.xlsx', '.pdf']:
                stat = file_path.stat()
                files.append({
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "extension": file_path.suffix
                })
        
        files.sort(key=lambda x: x["modified"], reverse=True)
        return files
        
    except Exception as e:
        log_with_context(logger, 'error', 'Failed to list data files', error=str(e))
        return []

@router.post("/generate-report", response_model=ReportResponse)
async def generate_financial_report(request: ReportRequest):
    """
    Generate comprehensive financial analysis report
    Creates PDF report with metrics and analytical questions
    """
    
    try:
        # Verify company exists and has data
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM financial_metrics WHERE company_id = %s", (request.company_id,))
                metric_count = cur.fetchone()[0]
                
                if metric_count == 0:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No financial data found for company_id {request.company_id}. Please upload data first."
                    )
        
        # Generate unique report filename
        timestamp = int(datetime.now().timestamp() * 1000)
        report_filename = f"report_{request.company_id}_{timestamp}.pdf"
        report_path = REPORTS_DIR / report_filename
        
        log_with_context(logger, 'info', 'Starting report generation', 
            company_id=request.company_id,
            report_path=str(report_path)
        )
        
        processing_steps = []
        
        # Generate report using integrated Python processing
        try:
            # Use the processor's generate_report method
            report_result = processor.generate_report(request.company_id, str(report_path))
            if not report_result.success:
                raise Exception(f"Report generation failed: {report_result.message}")
            
            processing_steps.append("✓ Financial data compiled")
            processing_steps.append("✓ Analytical questions included") 
            processing_steps.append("✓ PDF report generated")
            
            if not report_path.exists():
                raise Exception("Report file was not created successfully")
            
            log_with_context(logger, 'info', 'Report generation completed', 
                company_id=request.company_id,
                report_path=str(report_path),
                file_size=report_path.stat().st_size
            )
            
            return ReportResponse(
                message="Report generated successfully",
                company_id=request.company_id,
                report_filename=report_filename,
                report_path=str(report_path),
                processing_steps=processing_steps
            )
            
        except Exception as generation_error:
            log_with_context(logger, 'error', 'Report generation failed', 
                error=str(generation_error),
                company_id=request.company_id
            )
            
            raise HTTPException(
                status_code=500,
                detail=f"Report generation failed: {str(generation_error)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        log_with_context(logger, 'error', 'Report request failed', 
            error=str(e),
            company_id=request.company_id
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Report request failed: {str(e)}"
        )