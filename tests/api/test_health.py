"""
Test cases for health endpoint
"""

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "server" / "app"))

from app.api.v1.endpoints.health import router
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_health_endpoint_structure():
    """Test that health endpoint returns proper structure"""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "environment" in data
    assert "python_version" in data
    assert "database_connected" in data
    
    assert data["status"] in ["ok", "degraded"]
    assert isinstance(data["database_connected"], bool)


def test_server_info_endpoint():
    """Test server info endpoint returns proper data"""
    response = client.get("/api/info")
    assert response.status_code == 200
    
    data = response.json()
    assert data["server"] == "FastAPI"
    assert "version" in data
    assert "python_version" in data
    assert "endpoints" in data