"""
Main API v1 router
Consolidates all endpoint routers for the v1 API
"""

from fastapi import APIRouter

from .endpoints import upload, reports, health

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router)
api_router.include_router(upload.router) 
api_router.include_router(reports.router)