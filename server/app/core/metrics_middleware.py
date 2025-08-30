"""
FastAPI Middleware for Request Tracking and Metrics
"""

import time
import logging
from typing import Callable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .monitoring import (
    metrics, 
    enhanced_logger, 
    set_correlation_context, 
    clear_correlation_context,
    generate_correlation_id
)

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track request metrics and correlation IDs"""
    
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.logger = enhanced_logger
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Generate correlation ID
        correlation_id = generate_correlation_id()
        
        # Extract user context if available (from headers, auth, etc.)
        user_id = request.headers.get('X-User-ID', '')
        
        # Set correlation context
        set_correlation_context(correlation_id, user_id)
        
        # Add correlation ID to request state for access in endpoints
        request.state.correlation_id = correlation_id
        
        # Start timing
        start_time = time.time()
        
        # Request logging
        self.logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                'method': request.method,
                'url': str(request.url),
                'client_ip': request.client.host if request.client else 'unknown',
                'user_agent': request.headers.get('user-agent', ''),
                'correlation_id': correlation_id
            }
        )
        
        # Increment request counter
        metrics.increment_counter('http.requests.total', 1, {
            'method': request.method,
            'path': request.url.path
        })
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Record metrics
            metrics.record_timing('http.request.duration', duration_ms, {
                'method': request.method,
                'path': request.url.path,
                'status_code': str(response.status_code)
            })
            
            metrics.increment_counter('http.responses.total', 1, {
                'method': request.method,
                'path': request.url.path,
                'status_code': str(response.status_code)
            })
            
            # Response logging
            self.logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    'method': request.method,
                    'url': str(request.url),
                    'status_code': response.status_code,
                    'duration_ms': round(duration_ms, 2),
                    'correlation_id': correlation_id
                }
            )
            
            # Add correlation ID to response headers
            response.headers['X-Correlation-ID'] = correlation_id
            
        except Exception as e:
            # Calculate duration for error case
            duration_ms = (time.time() - start_time) * 1000
            
            # Record error metrics
            metrics.increment_counter('http.requests.errors', 1, {
                'method': request.method,
                'path': request.url.path,
                'error_type': type(e).__name__
            })
            
            metrics.record_timing('http.request.duration', duration_ms, {
                'method': request.method,
                'path': request.url.path,
                'status_code': '500'
            })
            
            # Error logging
            self.logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                extra={
                    'method': request.method,
                    'url': str(request.url),
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'duration_ms': round(duration_ms, 2),
                    'correlation_id': correlation_id
                },
                exc_info=True
            )
            
            raise
        
        finally:
            # Clear correlation context
            clear_correlation_context()
        
        return response

def add_metrics_middleware(app: FastAPI):
    """Add metrics middleware to FastAPI app"""
    app.add_middleware(MetricsMiddleware)
    
    # Start system metrics collection
    from .monitoring import system_metrics
    system_metrics.start(interval_seconds=60)
    
    enhanced_logger.info("Metrics middleware and system monitoring initialized")