"""
Upload endpoint for file processing
Handles file uploads and processing through the financial data pipeline
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks

from app.utils.utils import get_db_connection
from app.utils.logging_config import setup_logger, log_with_context
from app.services.pipeline_processor import FinancialDataProcessor
from app.models.api.responses import UploadResponse
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["upload"])
logger = setup_logger('financial-data-api')
processor = FinancialDataProcessor()

DATA_DIR = settings.project_root / "data"

@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_id: int = Form(...)
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