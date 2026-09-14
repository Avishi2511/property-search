"""Property search tools.

These are the primitives the agent calls — deliberately plain functions
(not classes) so they're easy to expose as LLM tool calls later. The agent
decides when to call each one; nothing here talks to the LLM.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.properties.repository import get_repository
from app.search.filters import SearchCriteria, apply_hard_filters
from app.search.geo import haversine_km

SAVED_SEARCHES_PATH = Path(__file__).parent.parent / "properties" / "data" / "saved_searches.json"

AVG_CITY_SPEED_KMPH = 22.0  # rough average accounting for Bangalore traffic


@dataclass
class SearchResult:
    total_matches: int
    properties: list[dict]  # page of matching properties, unranked (filter order preserved)


def search_properties(criteria: SearchCriteria, limit: int | None = 20) -> SearchResult:
    """Filters the full property set down to those satisfying every hard
    constraint in `criteria`. Does not rank/sort — that's the ranking
    layer's job (added in a later step); this just answers "how big is the
    remaining search space, and what's in it".
    """
    repo = get_repository()
    matches = apply_hard_filters(repo.all(), criteria)
    return SearchResult(
        total_matches=len(matches),
        properties=matches[:limit] if limit is not None else matches,
    )


def get_property(property_id: str) -> dict | None:
    return get_repository().get(property_id)


def compare_properties(property_ids: list[str]) -> dict:
    """Side-by-side comparison of a small set of properties on the fields
    that typically drive a buyer's decision.
    """
    repo = get_repository()
    found = [repo.get(pid) for pid in property_ids]
    missing = [pid for pid, p in zip(property_ids, found) if p is None]
    properties = [p for p in found if p is not None]

    fields = ["price", "bedrooms", "area_sqft", "possession", "location", "builder"]
    comparison = {field: {p["id"]: p[field] for p in properties} for field in fields}
    comparison["amenities"] = {p["id"]: p["amenities"] for p in properties}
    comparison["price_per_sqft"] = {
        p["id"]: round(p["price"] / p["area_sqft"], 2) for p in properties
    }

    return {
        "properties": properties,
        "comparison": comparison,
        "missing_ids": missing,
    }


def calculate_commute(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    avg_speed_kmph: float = AVG_CITY_SPEED_KMPH,
) -> dict:
    """Straight-line distance converted to a rough drive-time estimate.
    Good enough for ranking/filtering purposes in the MVP — not a routing engine.
    """
    distance_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    estimated_minutes = (distance_km / avg_speed_kmph) * 60
    return {
        "distance_km": round(distance_km, 2),
        "estimated_minutes": round(estimated_minutes),
    }


def find_nearby_places(
    lat: float,
    lng: float,
    category: str | None = None,
    radius_km: float = 5.0,
    limit: int = 5,
) -> list[dict]:
    """Named landmarks (hospitals, schools, metro stations, tech parks, malls)
    within `radius_km` of a point, nearest first. `category` filters to one
    of: hospital, school, metro, office_hub, mall.
    """
    repo = get_repository()
    results = []
    for landmark in repo.landmarks():
        if category is not None and landmark["category"] != category:
            continue
        distance_km = haversine_km(lat, lng, landmark["latitude"], landmark["longitude"])
        if distance_km <= radius_km:
            results.append({**landmark, "distance_km": round(distance_km, 2)})
    results.sort(key=lambda r: r["distance_km"])
    return results[:limit]


def save_search(buyer_id: str, criteria: SearchCriteria, total_matches: int) -> dict:
    """Persists a snapshot of a search (buyer id, criteria, result count) for
    later retrieval/analytics. Simple append-only JSON store — fine for the
    MVP's scale, swappable for a real database later.
    """
    SAVED_SEARCHES_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if SAVED_SEARCHES_PATH.exists():
        existing = json.loads(SAVED_SEARCHES_PATH.read_text(encoding="utf-8"))

    entry = {
        "buyer_id": buyer_id,
        "criteria": {k: v for k, v in criteria.__dict__.items() if v not in (None, [])},
        "total_matches": total_matches,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    existing.append(entry)
    SAVED_SEARCHES_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return entry
