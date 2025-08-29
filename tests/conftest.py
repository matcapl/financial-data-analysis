"""
Pytest configuration and shared fixtures
"""

import os
import pytest
import sys
from pathlib import Path

# Add server app to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

from app.core.config import settings


@pytest.fixture(scope="session")
def test_settings():
    """Test application settings"""
    # Override for test environment
    test_settings = settings.model_copy(update={
        "environment": "test",
        "debug": True
    })
    return test_settings


@pytest.fixture
def sample_csv_data():
    """Sample CSV data for testing"""
    return """Date,Description,Amount,Category
2023-01-01,Revenue from sales,10000.00,Revenue
2023-01-02,Office rent expense,-2000.00,Expense
2023-01-03,Marketing spend,-500.00,Marketing"""


@pytest.fixture
def sample_financial_data():
    """Sample financial data for testing"""
    return [
        {
            "date": "2023-01-01",
            "description": "Revenue from sales", 
            "amount": 10000.00,
            "category": "Revenue"
        },
        {
            "date": "2023-01-02",
            "description": "Office rent expense",
            "amount": -2000.00, 
            "category": "Expense"
        }
    ]