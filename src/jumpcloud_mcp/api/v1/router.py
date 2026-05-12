from fastapi import APIRouter

from jumpcloud_mcp.api.v1.endpoints.health import router as health_router
from jumpcloud_mcp.api.v1.endpoints.aggregations import router as aggregations_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(aggregations_router)
