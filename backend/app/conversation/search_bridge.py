"""Translates a BuyerProfile's *hard*-typed constraints into a SearchCriteria.

Soft/preference/context constraints never reach this function — they're
handled entirely by the ranking layer instead, so they narrow ordering, not
the candidate set. This is the one place that decision boundary is drawn.
"""
from __future__ import annotations

from app.constraints.schema import BuyerProfile
from app.properties.localities import LOCALITY_COORDS
from app.ranking.scorer import AVG_CITY_SPEED_KMPH
from app.search.filters import SearchCriteria


def build_search_criteria(profile: BuyerProfile) -> SearchCriteria:
    criteria = SearchCriteria()
    required_amenities: list[str] = []

    for field, c in profile.constraints.items():
        if c.type != "hard":
            continue

        if field == "city" and isinstance(c.value, str):
            criteria.city = c.value

        elif field == "bedrooms" and c.value is not None:
            criteria.bedrooms = c.value

        elif field == "budget":
            if c.min is not None:
                criteria.budget_min = c.min
            if c.max is not None:
                criteria.budget_max = c.max
            if c.value is not None and c.min is None and c.max is None:
                criteria.budget_min = criteria.budget_max = c.value

        elif field == "possession_date" and isinstance(c.value, str):
            criteria.possession_before = c.value

        elif field == "locality":
            if isinstance(c.value, str):
                criteria.locality = c.value
            elif isinstance(c.value, dict) and "near" in c.value:
                coords = LOCALITY_COORDS.get(str(c.value["near"]).lower())
                if coords is not None:
                    criteria.reference_lat, criteria.reference_lng = coords
                    max_minutes = c.value.get("max_minutes")
                    if max_minutes:
                        criteria.max_distance_km = (max_minutes / 60) * AVG_CITY_SPEED_KMPH

        elif field == "parking" and c.value is True:
            required_amenities.append("parking")

        elif field == "amenities" and isinstance(c.value, list):
            required_amenities.extend(c.value)

    criteria.required_amenities = required_amenities
    return criteria
