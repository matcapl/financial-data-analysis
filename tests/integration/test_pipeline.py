"""
Integration tests for the financial data processing pipeline
"""

import pytest
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "server" / "app" / "services"))

from pipeline_processor import FinancialDataProcessor


@pytest.fixture
def processor():
    """Fixture for financial data processor"""
    return FinancialDataProcessor()


@pytest.fixture
def sample_csv_file():
    """Create a temporary CSV file for testing"""
    content = """Date,Description,Amount,Category
2023-01-01,Revenue from sales,10000.00,Revenue
2023-01-02,Office rent expense,-2000.00,Expense
2023-01-03,Marketing spend,-500.00,Marketing"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(content)
        return f.name


def test_pipeline_processor_initialization(processor):
    """Test that processor initializes correctly"""
    assert processor is not None
    assert hasattr(processor, 'ingest_file')
    assert hasattr(processor, 'calculate_metrics')
    assert hasattr(processor, 'generate_findings')
    assert hasattr(processor, 'generate_report')


@pytest.mark.skip(reason="Requires database setup")
def test_file_ingestion(processor, sample_csv_file):
    """Test file ingestion process"""
    result = processor.ingest_file(sample_csv_file, company_id=999)
    
    # Note: This test requires database setup
    # Should pass with proper test database configuration
    assert hasattr(result, 'success')
    assert hasattr(result, 'message')