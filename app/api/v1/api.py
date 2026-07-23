from fastapi import APIRouter

from app.api.v1.endpoints import health as health_endpoint

api_router = APIRouter()
api_router.include_router(health_endpoint.router, prefix="/health", tags=["health"])
