"""Loads the synthetic property + landmark datasets and serves raw records.

Every other module (search, ranking, discovery) reads properties through
this repository rather than touching the JSON files directly, so the data
source can later be swapped (e.g. a real database) without touching callers.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


class PropertyRepository:
    def __init__(self, properties: list[dict], landmarks: list[dict]):
        self._properties = properties
        self._by_id = {p["id"]: p for p in properties}
        self._landmarks = landmarks

    def all(self) -> list[dict]:
        return self._properties

    def get(self, property_id: str) -> dict | None:
        return self._by_id.get(property_id)

    def landmarks(self) -> list[dict]:
        return self._landmarks


@lru_cache(maxsize=1)
def get_repository() -> PropertyRepository:
    properties = json.loads((DATA_DIR / "properties.json").read_text(encoding="utf-8"))
    landmarks = json.loads((DATA_DIR / "landmarks.json").read_text(encoding="utf-8"))
    return PropertyRepository(properties, landmarks)
