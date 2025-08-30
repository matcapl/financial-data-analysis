"""
Main API v1 router
Consolidates all endpoint routers for the v1 API
"""

from fastapi import APIRouter

from .endpoints import upload, reports, health, metrics, errors

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router)
api_router.include_router(upload.router) 
api_router.include_router(reports.router)
api_router.include_router(metrics.router, prefix="/monitoring", tags=["monitoring"])
api_router.include_router(errors.router, prefix="/monitoring", tags=["monitoring"])