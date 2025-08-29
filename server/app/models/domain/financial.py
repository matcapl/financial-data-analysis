"""
Financial domain models
Core business entities for financial data processing
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, field_validator


class MetricType(str, Enum):
    """Types of financial metrics"""
    REVENUE = "revenue"
    PROFIT = "profit"
    EXPENSE = "expense"
    CASH_FLOW = "cash_flow"
    RATIO = "ratio"


class Company(BaseModel):
    """Company entity"""
    id: int
    name: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class FinancialRecord(BaseModel):
    """Individual financial record from uploaded data"""
    id: Optional[int] = None
    company_id: int
    date: datetime
    description: str
    amount: Decimal
    category: Optional[str] = None
    subcategory: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if isinstance(v, str):
            try:
                return Decimal(v)
            except Exception:
                raise ValueError("Invalid amount format")
        return v
    
    class Config:
        from_attributes = True


class FinancialMetric(BaseModel):
    """Calculated financial metric"""
    id: Optional[int] = None
    company_id: int
    metric_name: str
    metric_type: MetricType
    value: Decimal
    period: str
    calculation_date: datetime
    metadata: Optional[dict] = None
    
    class Config:
        from_attributes = True


class AnalyticalQuestion(BaseModel):
    """Generated analytical question"""
    id: Optional[int] = None
    company_id: int
    question_text: str
    category: str
    priority: int = 1
    context: Optional[dict] = None
    created_at: Optional[datetime] = None
    
    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if not 1 <= v <= 5:
            raise ValueError("Priority must be between 1 and 5")
        return v
    
    class Config:
        from_attributes = True


class ProcessingResult(BaseModel):
    """Result of pipeline processing operations"""
    success: bool
    message: str
    company_id: Optional[int] = None
    records_processed: Optional[int] = None
    metrics_calculated: Optional[int] = None
    questions_generated: Optional[int] = None
    errors: Optional[List[str]] = None
    processing_time: Optional[float] = None