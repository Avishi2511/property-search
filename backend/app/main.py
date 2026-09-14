"""FastAPI entrypoint.

For now this only exposes a health check so we can verify the scaffold runs
end-to-end. Routers for /properties, /session, and the /ws/conversation
WebSocket are added in later steps as the corresponding modules are built.
"""
from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="Voice Search With Progressive Constraint Discovery")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "gemini_enabled": settings.gemini_enabled,
    }
