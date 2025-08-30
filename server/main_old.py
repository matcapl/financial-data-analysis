#!/usr/bin/env python3
"""
FastAPI Backend for Financial Data Analysis System
Consolidated single-backend architecture replacing Node.js + Python
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
import tempfile
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Add services directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent / "app" / "services"))

try:
    from utils import get_db_connection
    from logging_config import setup_logger, log_with_context
    from pipeline_processor import FinancialDataProcessor
    import calc_metrics
    import questions_engine
    import report_generator
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all required modules are available in server/app/services/")
    sys.exit(1)

# Initialize processor
processor = FinancialDataProcessor()

# Initialize FastAPI app
app = FastAPI(
    title="Financial Data Analysis API",
    description="Unified FastAPI backend for financial data processing and analysis",
    version="2.0.0"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging
logger = setup_logger('financial-data-api')

# Ensure directories exist
ROOT_DIR = Path(__file__).parent.parent  # Go up one level from server/ to project root
DATA_DIR = ROOT_DIR / "data"
REPORTS_DIR = ROOT_DIR / "reports"
UPLOADS_DIR = ROOT_DIR / "uploads"

for directory in [DATA_DIR, REPORTS_DIR, UPLOADS_DIR]:
    directory.mkdir(exist_ok=True)

# Pydantic models
class ReportRequest(BaseModel):
    company_id: int

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    environment: str
    python_version: str
    database_connected: bool

class UploadResponse(BaseModel):
    message: str
    filename: str
    company_id: Optional[int] = None
    processing_steps: List[str]
    file_path: Optional[str] = None

class ReportResponse(BaseModel):
    message: str
    company_id: int
    report_filename: str
    report_path: Optional[str] = None
    processing_steps: List[str]

# Serve static files
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with database connectivity test"""
    try:
        # Test database connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        db_connected = True
    except Exception as e:
        log_with_context(logger, 'warning', 'Database health check failed', error=str(e))
        db_connected = False
    
    return HealthResponse(
        status="ok" if db_connected else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        environment=os.getenv("NODE_ENV", "development"),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        database_connected=db_connected
    )

@app.get("/api/info")
async def server_info():
    """Server information endpoint"""
    return {
        "server": "FastAPI",
        "version": "2.0.0",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "environment": os.getenv("NODE_ENV", "development"),
        "endpoints": {
            "health": "/health",
            "upload": "/api/upload", 
            "generate_report": "/api/generate-report",
            "reports": "/api/reports",
            "data_files": "/api/data-files"
        }
    }

@app.get("/api/reports")
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

@app.get("/api/data-files")
async def list_data_files():
    """List uploaded data files for debugging/testing"""
    try:
        files = []
        for file_path in DATA_DIR.glob("*"):
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

@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_id: Optional[int] = 1
):
    """
    Upload and process financial data files
    Supports CSV, XLSX, and PDF files with comprehensive pipeline processing
    """
    
    # Validate file type
    allowed_extensions = {'.csv', '.xlsx', '.pdf'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file_ext}. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Validate file size (10MB limit)
    max_size = 10 * 1024 * 1024  # 10MB
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 10MB."
        )
    
    try:
        # Generate unique filename
        timestamp = int(datetime.now().timestamp() * 1000)
        safe_filename = f"{timestamp}_{Path(file.filename).name}"
        file_path = DATA_DIR / safe_filename
        
        # Save file
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        log_with_context(logger, 'info', 'File uploaded', 
            filename=file.filename,
            size=len(file_content),
            path=str(file_path),
            company_id=company_id
        )
        
        # Process file through complete pipeline
        processing_steps = []
        
        try:
            # Step 1: Data Ingestion
            log_with_context(logger, 'info', 'Starting pipeline processing', 
                file_path=str(file_path),
                company_id=company_id
            )
            
            ingest_result = processor.ingest_file(str(file_path), company_id)
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
            
            log_with_context(logger, 'info', 'Pipeline processing completed', 
                company_id=company_id,
                file_path=str(file_path),
                steps=len(processing_steps)
            )
            
            return UploadResponse(
                message="File processed successfully! All pipeline steps completed.",
                filename=file.filename,
                company_id=company_id,
                processing_steps=processing_steps,
                file_path=str(file_path)
            )
            
        except Exception as processing_error:
            log_with_context(logger, 'error', 'Pipeline processing failed', 
                error=str(processing_error),
                company_id=company_id,
                file_path=str(file_path)
            )
            
            # Clean up uploaded file on processing failure
            if file_path.exists():
                file_path.unlink()
            
            raise HTTPException(
                status_code=422,
                detail=f"File processing failed: {str(processing_error)}"
            )
            
    except Exception as e:
        log_with_context(logger, 'error', 'Upload failed', 
            error=str(e),
            filename=file.filename
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )

@app.post("/api/generate-report", response_model=ReportResponse)
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

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not found",
            "path": str(request.url.path),
            "available_endpoints": [
                "GET /health",
                "GET /api/info", 
                "GET /api/reports",
                "GET /api/data-files",
                "POST /api/upload",
                "POST /api/generate-report"
            ]
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    log_with_context(logger, 'error', 'Internal server error', 
        path=str(request.url.path),
        error=str(exc)
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }
    )

if __name__ == "__main__":
    # Environment configuration
    port = int(os.getenv("PORT", 4000))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("NODE_ENV", "development") != "production"
    
    log_with_context(logger, 'info', 'Starting FastAPI server', 
        host=host,
        port=port,
        debug=debug,
        environment=os.getenv("NODE_ENV", "development")
    )
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        access_log=True
    )