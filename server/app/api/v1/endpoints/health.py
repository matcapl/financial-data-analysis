"""
Health endpoint for system status and monitoring
Provides health checks and server information
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List

from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils import get_db_connection
from logging_config import setup_logger, log_with_context
from app.models.api.responses import HealthResponse

router = APIRouter(tags=["health"])
logger = setup_logger('financial-data-api')

@router.get("/health", response_model=HealthResponse)
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

@router.get("/api/info")
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