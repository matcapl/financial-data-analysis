"""
Error Tracking API endpoints
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException, Path
from pydantic import BaseModel

from ....core.error_tracking import error_tracker
from ....models.api.responses import BaseResponse

router = APIRouter()

class ErrorSummaryResponse(BaseModel):
    """Response model for error summary"""
    total_errors: int
    unique_errors: int
    error_types: Dict[str, int]
    top_errors: list
    time_range_hours: int
    generated_at: str

class ErrorDetailsResponse(BaseModel):
    """Response model for error details"""
    error_details: Dict[str, Any]
    occurrence_count: int
    first_seen: str
    related_errors: list

@router.get("/errors/summary", response_model=ErrorSummaryResponse)
async def get_error_summary(
    hours: int = Query(24, description="Time range in hours", ge=1, le=168)
):
    """
    Get error summary for the specified time range
    
    - **hours**: Time range in hours (1-168, max 1 week)
    """
    try:
        summary = error_tracker.get_error_summary(hours=hours)
        return ErrorSummaryResponse(
            total_errors=summary['total_errors'],
            unique_errors=summary['unique_errors'],
            error_types=summary['error_types'],
            top_errors=summary['top_errors'],
            time_range_hours=summary['time_range_hours'],
            generated_at=summary['generated_at']
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve error summary: {str(e)}")

@router.get("/errors/{error_id}", response_model=ErrorDetailsResponse)
async def get_error_details(
    error_id: str = Path(..., description="Error ID to retrieve details for")
):
    """
    Get detailed information about a specific error
    
    - **error_id**: The unique identifier for the error
    """
    try:
        details = error_tracker.get_error_details(error_id)
        
        if not details:
            raise HTTPException(status_code=404, detail=f"Error {error_id} not found")
        
        return ErrorDetailsResponse(**details)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve error details: {str(e)}")

@router.get("/errors/slow-operations")
async def get_slow_operations(
    limit: int = Query(10, description="Number of slow operations to return", ge=1, le=100)
):
    """
    Get the slowest operations recorded
    
    - **limit**: Maximum number of operations to return
    """
    try:
        from ....core.performance_monitor import profiler
        
        slow_ops = profiler.get_top_slow_operations(limit=limit)
        
        return {
            'slow_operations': slow_ops,
            'limit': limit,
            'total_found': len(slow_ops)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve slow operations: {str(e)}")

@router.post("/errors/{error_id}/resolve")
async def mark_error_resolved(
    error_id: str = Path(..., description="Error ID to mark as resolved")
):
    """
    Mark an error as resolved
    
    - **error_id**: The unique identifier for the error
    """
    try:
        success = error_tracker.mark_error_resolved(error_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Error {error_id} not found")
        
        return {
            "message": f"Error {error_id} marked as resolved",
            "error_id": error_id,
            "resolved": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve error: {str(e)}")

@router.delete("/errors/cleanup")
async def cleanup_old_errors(
    days: int = Query(30, description="Delete errors older than this many days", ge=1, le=365)
):
    """
    Clean up old error records
    
    - **days**: Delete errors older than this many days
    """
    try:
        deleted_count = error_tracker.clear_old_errors(days=days)
        
        return {
            "message": f"Cleaned up {deleted_count} old error records",
            "deleted_count": deleted_count,
            "cutoff_days": days
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup errors: {str(e)}")

@router.get("/errors/alerts")
async def get_recent_alerts(
    hours: int = Query(24, description="Time range in hours", ge=1, le=168)
):
    """
    Get recent alerts from error tracking
    """
    try:
        from pathlib import Path
        import json
        from datetime import datetime, timedelta
        
        logs_dir = Path(__file__).parent.parent.parent.parent.parent.parent / 'logs'
        alert_log = logs_dir / 'alerts.jsonl'
        
        if not alert_log.exists():
            return {'alerts': [], 'count': 0}
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_alerts = []
        
        with open(alert_log, 'r') as f:
            for line in f:
                try:
                    alert = json.loads(line.strip())
                    alert_time = datetime.fromisoformat(alert['timestamp'])
                    if alert_time >= cutoff:
                        recent_alerts.append(alert)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        
        # Sort by timestamp (newest first)
        recent_alerts.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {
            'alerts': recent_alerts,
            'count': len(recent_alerts),
            'time_range_hours': hours
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve alerts: {str(e)}")