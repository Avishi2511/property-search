"""FastAPI entrypoint.

For now this only exposes a health check so we can verify the scaffold runs
end-to-end. Routers for /properties, /session, and the /ws/conversation
WebSocket are added in later steps as the corresponding modules are built.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ws import router as ws_router
from app.config import settings

app = FastAPI(title="Voice Search With Progressive Constraint Discovery")

# Dev-friendly CORS: the frontend runs on a different origin (Vite dev server).
# Fine for this portfolio project; tighten allow_origins before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "gemini_enabled": settings.gemini_enabled,
    }
