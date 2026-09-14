"""Hard-constraint filtering.

`SearchCriteria` is a plain, constraint-schema-agnostic set of filter knobs.
Callers (the conversation manager, in a later step) decide which fields to
populate based on which of the buyer's constraints are actually "hard" —
soft preferences are handled by the ranking layer instead, not here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.search.geo import haversine_km


@dataclass
class SearchCriteria:
    city: str | None = None
    bedrooms: int | None = None          # exact match
    bedrooms_min: int | None = None      # at least this many
    budget_min: float | None = None
    budget_max: float | None = None
    possession_before: str | None = None  # "YYYY-MM", inclusive upper bound
    required_amenities: list[str] = field(default_factory=list)
    locality: str | None = None          # exact locality/location name match

    # Hard commute/proximity constraint, e.g. "must be within 45 min of Koramangala".
    reference_lat: float | None = None
    reference_lng: float | None = None
    max_distance_km: float | None = None


def matches(prop: dict, criteria: SearchCriteria) -> bool:
    if criteria.city and prop["city"].lower() != criteria.city.lower():
        return False

    if criteria.bedrooms is not None and prop["bedrooms"] != criteria.bedrooms:
        return False

    if criteria.bedrooms_min is not None and prop["bedrooms"] < criteria.bedrooms_min:
        return False

    if criteria.budget_min is not None and prop["price"] < criteria.budget_min:
        return False

    if criteria.budget_max is not None and prop["price"] > criteria.budget_max:
        return False

    if criteria.possession_before is not None and prop["possession"] > criteria.possession_before:
        return False

    if criteria.locality and prop["location"].lower() != criteria.locality.lower():
        return False

    if criteria.required_amenities:
        prop_amenities = set(prop["amenities"])
        if not set(criteria.required_amenities).issubset(prop_amenities):
            return False

    if criteria.max_distance_km is not None:
        if criteria.reference_lat is None or criteria.reference_lng is None:
            raise ValueError("max_distance_km requires reference_lat/reference_lng")
        distance = haversine_km(
            prop["latitude"], prop["longitude"], criteria.reference_lat, criteria.reference_lng
        )
        if distance > criteria.max_distance_km:
            return False

    return True


def apply_hard_filters(properties: list[dict], criteria: SearchCriteria) -> list[dict]:
    return [p for p in properties if matches(p, criteria)]
