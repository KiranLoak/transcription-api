from fastapi import APIRouter

from app.api.v1.endpoints import health, keys, transcriptions, usage

api_router = APIRouter()
api_router.include_router(transcriptions.router)
api_router.include_router(keys.router)
api_router.include_router(usage.router)
