"""
API response models  
Pydantic models for API response serialization
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class BaseResponse(BaseModel):
    """Base response model for API responses"""
    success: bool = True
    message: Optional[str] = None
    timestamp: str = datetime.utcnow().isoformat()


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    environment: str
    python_version: str
    database_connected: bool


class UploadResponse(BaseModel):
    """File upload response"""
    message: str
    filename: str
    company_id: Optional[int] = None
    processing_steps: List[str]
    file_path: Optional[str] = None


class ReportResponse(BaseModel):
    """Report generation response"""
    message: str
    company_id: int
    report_filename: str
    report_path: Optional[str] = None
    processing_steps: List[str]


class ReportListItem(BaseModel):
    """Individual report in list response"""
    id: str
    filename: str
    url: str
    created: str
    size: int


class DataFileListItem(BaseModel):
    """Individual data file in list response"""
    filename: str
    size: int
    modified: str
    extension: str


class ServerInfo(BaseModel):
    """Server information response"""
    server: str
    version: str
    python_version: str
    environment: str
    endpoints: Dict[str, str]