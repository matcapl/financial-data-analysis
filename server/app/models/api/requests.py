"""
API request models
Pydantic models for API request validation
"""

from typing import Optional, List
from pydantic import BaseModel, field_validator


class ReportRequest(BaseModel):
    """Request for generating a financial report"""
    company_id: int
    
    @field_validator("company_id")
    @classmethod
    def validate_company_id(cls, v):
        if v <= 0:
            raise ValueError("Company ID must be positive")
        return v


class FileUploadRequest(BaseModel):
    """Request parameters for file upload (used for validation)"""
    company_id: Optional[int] = 1
    
    @field_validator("company_id")
    @classmethod
    def validate_company_id(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Company ID must be positive")
        return v