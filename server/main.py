#!/usr/bin/env python3
"""
FastAPI Backend for Financial Data Analysis System
Consolidated single-backend architecture replacing Node.js + Python
"""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Add app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.core.config import settings
from app.api.v1.router import api_router
from app.services.logging_config import setup_logger, log_with_context

# Initialize FastAPI app
app = FastAPI(
    title=settings.title,
    description=settings.description,
    version=settings.version
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=settings.security.cors_allow_credentials,
    allow_methods=settings.security.cors_allow_methods,
    allow_headers=settings.security.cors_allow_headers,
)

# Setup logging
logger = setup_logger('financial-data-api')

# Ensure directories exist
for directory in [settings.project_root / "data", settings.project_root / "reports", settings.project_root / "uploads"]:
    directory.mkdir(exist_ok=True)

# Serve static files
app.mount("/reports", StaticFiles(directory=str(settings.project_root / "reports")), name="reports")

# Include API router
app.include_router(api_router)

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
    log_with_context(logger, 'info', 'Starting FastAPI server', 
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        environment=settings.environment
    )
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        access_log=True
    )