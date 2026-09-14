"""Central app configuration, loaded from environment variables.

Keeping this in one place means every module that needs the Gemini key or
server settings imports from here instead of calling os.environ directly.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    @property
    def gemini_enabled(self) -> bool:
        return self.gemini_api_key is not None


settings = Settings()
