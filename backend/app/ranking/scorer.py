"""Deterministic soft-preference ranking.

Hard constraints are expected to have already been applied as a filter
(see search/filters.py) before candidates reach this module — but as a
defense-in-depth measure, `rank_properties` also drops anything that would
violate a *hard*-typed constraint on the profile, so ranking can never
promote a property the buyer explicitly ruled out.

Every soft factor below produces a 0..1 sub-score; the final score is a
weighted average over only the factors that are actually applicable given
what's known about the buyer (so an unanswered question doesn't silently
drag every property's score down). Each factor's weight is additionally
scaled by that constraint's confidence, so a shaky, low-confidence
preference influences ranking less than a firmly stated one.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.constraints.schema import BuyerProfile, ConstraintValue
from app.properties.localities import LOCALITY_COORDS
from app.search.geo import haversine_km

AVG_CITY_SPEED_KMPH = 22.0

BASE_WEIGHTS = {
    "budget_fit": 25,
    "locality": 20,
    "possession": 15,
    "commute": 12,
    "hospital_access": 12,
    "amenities": 8,
    "parking": 5,
    "builder_preference": 3,
}

_PRIORITY_MULTIPLIER = {"low": 0.4, "medium": 1.0, "high": 1.6}


@dataclass
class RankedProperty:
    property: dict
    score: float                    # 0..100
    breakdown: dict[str, float]     # factor -> 0..1 sub-score, for explainability


def _violates_hard_constraints(prop: dict, profile: BuyerProfile) -> bool:
    for field, c in profile.constraints.items():
        if c.type != "hard":
            continue
        if field == "city" and c.value and prop["city"].lower() != str(c.value).lower():
            return True
        if field == "bedrooms" and c.value is not None and prop["bedrooms"] != c.value:
            return True
        if field == "budget":
            lo = c.min if c.min is not None else c.value
            hi = c.max if c.max is not None else c.value
            if lo is not None and prop["price"] < lo:
                return True
            if hi is not None and prop["price"] > hi:
                return True
        if field == "possession_date" and c.value and prop["possession"] > c.value:
            return True
        if field == "locality" and isinstance(c.value, str) and prop["location"].lower() != c.value.lower():
            return True
    return False


def _budget_fit(prop: dict, budget: ConstraintValue) -> float:
    price = prop["price"]
    lo = budget.min if budget.min is not None else budget.value
    hi = budget.max if budget.max is not None else budget.value
    if lo is None and hi is None:
        return 0.5
    if lo is None:
        lo = hi
    if hi is None:
        hi = lo

    if lo <= price <= hi:
        # Inside the stated range: reward being close to the midpoint slightly,
        # but any in-range price is already a strong fit.
        mid = (lo + hi) / 2
        span = max(hi - lo, 1)
        return 1.0 - 0.2 * (abs(price - mid) / span)

    # Outside the range: soft penalty proportional to how far outside, relative
    # to the range's own size (a ₹1L overshoot on a ₹2Cr budget barely matters).
    reference = max(hi - lo, hi * 0.1, 1)
    overshoot = (lo - price) if price < lo else (price - hi)
    return max(0.0, 1.0 - overshoot / reference)


def _possession_fit(prop: dict, possession: ConstraintValue) -> float:
    if not isinstance(possession.value, str):
        return 0.5
    return 1.0 if prop["possession"] <= possession.value else max(
        0.0, 1.0 - _month_diff(prop["possession"], possession.value) / 24
    )


def _month_diff(a: str, b: str) -> int:
    ay, am = map(int, a.split("-"))
    by, bm = map(int, b.split("-"))
    return abs((ay * 12 + am) - (by * 12 + bm))


def _distance_score(prop: dict, target_lat: float, target_lng: float, generous_km: float = 12.0) -> float:
    distance = haversine_km(prop["latitude"], prop["longitude"], target_lat, target_lng)
    return max(0.0, 1.0 - distance / generous_km)


def _resolve_place_coords(value) -> tuple[float, float] | None:
    """Resolves a locality-like constraint value (a plain name, or a
    {"near": name, "max_minutes": N} relaxation) to lat/lng, if possible.
    """
    if isinstance(value, str):
        return LOCALITY_COORDS.get(value.lower())
    if isinstance(value, dict) and "near" in value:
        return LOCALITY_COORDS.get(str(value["near"]).lower())
    return None


def _locality_fit(prop: dict, locality: ConstraintValue) -> float | None:
    if isinstance(locality.value, str):
        if prop["location"].lower() == locality.value.lower():
            return 1.0
        coords = _resolve_place_coords(locality.value)
        return _distance_score(prop, *coords) if coords else None

    if isinstance(locality.value, dict) and "near" in locality.value:
        coords = _resolve_place_coords(locality.value)
        if coords is None:
            return None
        max_minutes = locality.value.get("max_minutes")
        distance_km = haversine_km(prop["latitude"], prop["longitude"], *coords)
        if max_minutes:
            max_km = (max_minutes / 60) * AVG_CITY_SPEED_KMPH
            return max(0.0, min(1.0, 1.0 - distance_km / max_km)) if max_km else None
        return _distance_score(prop, *coords)

    return None


def _amenities_fit(prop: dict, amenities: ConstraintValue) -> float | None:
    if not isinstance(amenities.value, list) or not amenities.value:
        return None
    have = set(prop["amenities"])
    wanted = set(amenities.value)
    return len(wanted & have) / len(wanted)


def _parking_fit(prop: dict, parking: ConstraintValue) -> float:
    has_parking = "parking" in prop["amenities"]
    if parking.value is True:
        return 1.0 if has_parking else 0.0
    if parking.value is False:
        return 1.0
    return 0.5


def _builder_fit(prop: dict, builder: ConstraintValue) -> float | None:
    if not isinstance(builder.value, str):
        return None
    return 1.0 if prop["builder"].lower() == builder.value.lower() else 0.3


def _commute_and_hospital(prop: dict, profile: BuyerProfile) -> dict[str, float]:
    scores: dict[str, float] = {}
    office = profile.constraints.get("office_location")
    commute_priority = profile.constraints.get("buyer_commute")
    if office is not None and isinstance(office.value, str):
        coords = LOCALITY_COORDS.get(office.value.lower())
        if coords is not None:
            base = _distance_score(prop, *coords)
            weight_scale = _PRIORITY_MULTIPLIER.get(
                commute_priority.value if commute_priority else "medium", 1.0
            )
            scores["commute"] = base
            scores["_commute_weight_scale"] = weight_scale

    hospital_priority = profile.constraints.get("hospital_access")
    if hospital_priority is not None:
        distance = prop["nearby"]["hospital"]
        base = max(0.0, 1.0 - distance / 6.0)
        weight_scale = _PRIORITY_MULTIPLIER.get(hospital_priority.value, 1.0)
        scores["hospital_access"] = base
        scores["_hospital_weight_scale"] = weight_scale

    return scores


def score_property(prop: dict, profile: BuyerProfile) -> tuple[float, dict[str, float]]:
    constraints = profile.constraints
    breakdown: dict[str, float] = {}
    weighted_sum = 0.0
    total_weight = 0.0

    def add(factor: str, sub_score: float | None, confidence: float = 1.0, weight_scale: float = 1.0):
        """Blends `sub_score` toward neutral (0.5) by how confident we are in
        the underlying constraint, so a shaky guess pulls the aggregate
        toward "unknown" rather than swinging it as hard as a firm statement
        would. `weight_scale` (priority) instead changes how much this
        factor counts relative to others, independent of confidence.
        """
        nonlocal weighted_sum, total_weight
        if sub_score is None:
            return
        blended = 0.5 + confidence * (sub_score - 0.5)
        weight = BASE_WEIGHTS[factor] * weight_scale
        breakdown[factor] = round(sub_score, 3)
        weighted_sum += blended * weight
        total_weight += weight

    budget = constraints.get("budget")
    if budget is not None:
        add("budget_fit", _budget_fit(prop, budget), confidence_scale(budget))

    locality = constraints.get("locality")
    if locality is not None:
        add("locality", _locality_fit(prop, locality), confidence_scale(locality))

    possession = constraints.get("possession_date")
    if possession is not None:
        add("possession", _possession_fit(prop, possession), confidence_scale(possession))

    amenities = constraints.get("amenities")
    if amenities is not None:
        add("amenities", _amenities_fit(prop, amenities), confidence_scale(amenities))

    parking = constraints.get("parking")
    if parking is not None:
        add("parking", _parking_fit(prop, parking), confidence_scale(parking))

    builder = constraints.get("builder_preference")
    if builder is not None:
        add("builder_preference", _builder_fit(prop, builder), confidence_scale(builder))

    ch_scores = _commute_and_hospital(prop, profile)
    if "commute" in ch_scores:
        add("commute", ch_scores["commute"], weight_scale=ch_scores["_commute_weight_scale"])
    if "hospital_access" in ch_scores:
        add("hospital_access", ch_scores["hospital_access"], weight_scale=ch_scores["_hospital_weight_scale"])

    if total_weight == 0:
        return 50.0, breakdown  # nothing known yet to differentiate on
    return round(100 * weighted_sum / total_weight, 2), breakdown


def confidence_scale(c: ConstraintValue) -> float:
    """Low-confidence preferences influence ranking less."""
    return max(0.3, c.confidence)


def rank_properties(candidates: list[dict], profile: BuyerProfile) -> list[RankedProperty]:
    survivors = [p for p in candidates if not _violates_hard_constraints(p, profile)]
    ranked = []
    for prop in survivors:
        score, breakdown = score_property(prop, profile)
        ranked.append(RankedProperty(property=prop, score=score, breakdown=breakdown))
    # Deterministic ordering: score desc, then price asc, then id asc as a final tiebreaker.
    ranked.sort(key=lambda r: (-r.score, r.property["price"], r.property["id"]))
    return ranked
