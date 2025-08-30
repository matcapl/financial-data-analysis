"""
Metrics API endpoints for monitoring and observability
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from ....core.monitoring import metrics, system_metrics
from ....models.api.responses import BaseResponse

router = APIRouter()

class MetricsResponse(BaseModel):
    """Response model for metrics data"""
    metrics: Dict[str, Any]
    time_range_minutes: int
    collected_at: str

class HealthMetricsResponse(BaseModel):
    """Response model for health metrics"""
    status: str
    uptime_seconds: float
    system_metrics: Dict[str, Any]
    application_metrics: Dict[str, Any]

@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    name: Optional[str] = Query(None, description="Specific metric name to retrieve"),
    minutes: int = Query(60, description="Time range in minutes", ge=1, le=1440)
):
    """
    Get application metrics summary
    
    - **name**: Optional specific metric name
    - **minutes**: Time range in minutes (1-1440)
    """
    try:
        from datetime import datetime
        
        summary = metrics.get_metrics_summary(name=name, minutes=minutes)
        
        return MetricsResponse(
            metrics=summary,
            time_range_minutes=minutes,
            collected_at=datetime.utcnow().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")

@router.get("/metrics/health", response_model=HealthMetricsResponse)
async def get_health_metrics():
    """
    Get comprehensive health and system metrics
    """
    try:
        import time
        import psutil
        from datetime import datetime
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        system_info = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used_mb': round(memory.used / 1024 / 1024, 2),
            'memory_available_mb': round(memory.available / 1024 / 1024, 2),
            'disk_percent': round((disk.used / disk.total) * 100, 2),
            'disk_used_gb': round(disk.used / 1024 / 1024 / 1024, 2),
            'disk_free_gb': round(disk.free / 1024 / 1024 / 1024, 2)
        }
        
        # Get application metrics summary (last 10 minutes)
        app_metrics = metrics.get_metrics_summary(minutes=10)
        
        # Determine overall health status
        status = "healthy"
        if cpu_percent > 90 or memory.percent > 90:
            status = "degraded"
        if cpu_percent > 95 or memory.percent > 95:
            status = "unhealthy"
        
        return HealthMetricsResponse(
            status=status,
            uptime_seconds=time.time() - psutil.Process().create_time(),
            system_metrics=system_info,
            application_metrics=app_metrics
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve health metrics: {str(e)}")

@router.get("/metrics/requests")
async def get_request_metrics(
    minutes: int = Query(60, description="Time range in minutes", ge=1, le=1440)
):
    """
    Get HTTP request metrics summary
    """
    try:
        from datetime import datetime
        
        # Get request-related metrics
        request_metrics = {}
        all_metrics = metrics.get_metrics_summary(minutes=minutes)
        
        for metric_name, data in all_metrics.items():
            if 'http.' in metric_name or 'request' in metric_name.lower():
                request_metrics[metric_name] = data
        
        return {
            'request_metrics': request_metrics,
            'time_range_minutes': minutes,
            'collected_at': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve request metrics: {str(e)}")

@router.get("/metrics/errors")
async def get_error_metrics(
    minutes: int = Query(60, description="Time range in minutes", ge=1, le=1440)
):
    """
    Get error metrics summary
    """
    try:
        from datetime import datetime
        
        # Get error-related metrics
        error_metrics = {}
        all_metrics = metrics.get_metrics_summary(minutes=minutes)
        
        for metric_name, data in all_metrics.items():
            if 'error' in metric_name.lower() or 'exception' in metric_name.lower():
                error_metrics[metric_name] = data
        
        return {
            'error_metrics': error_metrics,
            'time_range_minutes': minutes,
            'collected_at': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve error metrics: {str(e)}")

@router.post("/metrics/reset")
async def reset_metrics():
    """
    Reset all application metrics (admin endpoint)
    """
    try:
        # Clear in-memory metrics
        with metrics.lock:
            metrics.metrics.clear()
        
        return {"message": "Metrics reset successfully", "timestamp": datetime.utcnow().isoformat()}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset metrics: {str(e)}")