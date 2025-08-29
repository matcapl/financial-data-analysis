"""
Test cases for domain models
"""

import pytest
from datetime import datetime
from decimal import Decimal

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "server" / "app"))

from app.models.domain.financial import FinancialRecord, FinancialMetric, MetricType, AnalyticalQuestion
from app.models.api.requests import ReportRequest
from app.models.api.responses import UploadResponse


def test_financial_record_validation():
    """Test FinancialRecord model validation"""
    record = FinancialRecord(
        company_id=1,
        date=datetime.now(),
        description="Test transaction",
        amount="1000.50",
        category="Revenue"
    )
    
    assert record.company_id == 1
    assert isinstance(record.amount, Decimal)
    assert record.amount == Decimal("1000.50")


def test_financial_record_invalid_amount():
    """Test FinancialRecord rejects invalid amounts"""
    with pytest.raises(ValueError):
        FinancialRecord(
            company_id=1,
            date=datetime.now(),
            description="Test",
            amount="invalid_amount"
        )


def test_financial_metric_creation():
    """Test FinancialMetric model creation"""
    metric = FinancialMetric(
        company_id=1,
        metric_name="Total Revenue",
        metric_type=MetricType.REVENUE,
        value=Decimal("50000.00"),
        period="2023-Q1",
        calculation_date=datetime.now()
    )
    
    assert metric.metric_type == MetricType.REVENUE
    assert isinstance(metric.value, Decimal)


def test_analytical_question_priority_validation():
    """Test AnalyticalQuestion priority validation"""
    # Valid priority
    question = AnalyticalQuestion(
        company_id=1,
        question_text="What drives revenue growth?",
        category="Growth",
        priority=3
    )
    assert question.priority == 3
    
    # Invalid priority
    with pytest.raises(ValueError):
        AnalyticalQuestion(
            company_id=1,
            question_text="Test question",
            category="Test",
            priority=10  # Invalid: must be 1-5
        )


def test_report_request_validation():
    """Test ReportRequest validation"""
    # Valid request
    request = ReportRequest(company_id=1)
    assert request.company_id == 1
    
    # Invalid company_id
    with pytest.raises(ValueError):
        ReportRequest(company_id=0)


def test_upload_response_creation():
    """Test UploadResponse model creation"""
    response = UploadResponse(
        message="Upload successful",
        filename="test.csv",
        company_id=1,
        processing_steps=["Step 1", "Step 2"],
        file_path="/path/to/file.csv"
    )
    
    assert response.message == "Upload successful"
    assert response.company_id == 1
    assert len(response.processing_steps) == 2