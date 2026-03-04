from fastapi import APIRouter

from app.api.endpoints import health, upload, reconcile, results, history, chat, ws, storage

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(storage.router, tags=["storage"])
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(reconcile.router, tags=["reconcile"])
api_router.include_router(results.router, tags=["results"])
api_router.include_router(history.router, tags=["history"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(ws.router, tags=["websocket"])
