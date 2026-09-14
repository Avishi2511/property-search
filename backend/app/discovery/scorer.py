"""Heuristic question scoring: estimates how useful each candidate question
would be, given the current candidate property set and buyer profile.

    question_score = expected_filter_strength * buyer_relevance * uncertainty * priority

This is deliberately a heuristic (per the spec, exact information-gain /
entropy-over-outcomes modeling is explicitly out of scope for the MVP) but
it's built as a `QuestionScorer` interface so a more rigorous algorithm can
be swapped in later without touching `policy.py`.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Protocol

from app.constraints.schema import BuyerProfile
from app.discovery.questions import PRIORITY_WEIGHTS

# Maps a trackable field to the property-record key it can be checked
# against, when the field corresponds to something actually stored on a
# property. Fields with no entry here don't filter the hard search space —
# they only affect ranking/ordering (e.g. commute priority) — and get a
# small constant "still worth asking" strength instead.
FIELD_TO_PROPERTY_KEY: dict[str, str] = {
    "city": "city",
    "bedrooms": "bedrooms",
    "budget": "price",
    "locality": "location",
    "possession_date": "possession",
    "builder_preference": "builder",
}

NON_FILTERABLE_BASE_STRENGTH = 0.15  # ranking-only fields (purpose, priorities, office location, ...)
CONFIDENCE_THRESHOLD = 0.85          # below this, a field is still worth re-asking/refining
RANGE_SPREAD_THRESHOLD = 0.15        # a budget range wider than this (relative) is still "unresolved"


def _normalized_entropy(values: list) -> float:
    """Shannon entropy of a categorical distribution, normalized to [0, 1]
    by the maximum possible entropy for that many distinct values. 0 means
    "everyone already has the same value" (asking is useless); 1 means
    "values are as spread out as possible" (asking splits the set well).
    """
    n = len(values)
    counts = Counter(values)
    if n <= 1 or len(counts) <= 1:
        return 0.0
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values())
    max_entropy = math.log2(len(counts))
    return entropy / max_entropy if max_entropy > 0 else 0.0


def _quantile_bin_entropy(values: list[float], bins: int = 4) -> float:
    """For ordinal/continuous values (price, dates-as-numbers): bins into
    `bins` equal-frequency buckets by rank, then measures entropy over bin
    membership. This models a buyer's answer as roughly a threshold split
    rather than treating every distinct number as its own category.
    """
    n = len(values)
    if n <= 1:
        return 0.0
    order = sorted(range(n), key=lambda i: values[i])
    bin_of = [0] * n
    for rank, idx in enumerate(order):
        bin_of[idx] = min(bins - 1, (rank * bins) // n)
    return _normalized_entropy(bin_of)


def _possession_to_ordinal(possession: str) -> int:
    year, month = possession.split("-")
    return int(year) * 12 + int(month)


def expected_filter_strength(field: str, candidates: list[dict]) -> float:
    """0..1 estimate of how much answering this question would narrow (or at
    least meaningfully reorder) the current candidate set.
    """
    if len(candidates) <= 1:
        return 0.0

    if field == "amenities":
        # Generic "any amenities you care about" — proxy with the average
        # spread across a few common amenity types (does having vs. not
        # having them roughly split the candidate set?).
        sample_amenities = ["pool", "gym", "clubhouse", "jogging_track"]
        strengths = []
        for amenity in sample_amenities:
            membership = [amenity in p["amenities"] for p in candidates]
            strengths.append(_normalized_entropy(membership))
        return sum(strengths) / len(strengths) if strengths else 0.0

    if field == "parking":
        membership = ["parking" in p["amenities"] for p in candidates]
        return _normalized_entropy(membership)

    property_key = FIELD_TO_PROPERTY_KEY.get(field)
    if property_key is None:
        return NON_FILTERABLE_BASE_STRENGTH

    if property_key == "price":
        return _quantile_bin_entropy([p["price"] for p in candidates])
    if property_key == "possession":
        return _quantile_bin_entropy([_possession_to_ordinal(p["possession"]) for p in candidates])

    return _normalized_entropy([p[property_key] for p in candidates])


def buyer_relevance(field: str, profile: BuyerProfile) -> float:
    """Contextual relevance multiplier: some questions only make sense once
    other information is known (e.g. hospital access matters more once we
    know the buyer's parents are moving in).
    """
    constraints = profile.constraints

    if field == "hospital_access":
        parents = constraints.get("parents_living_with_buyer")
        if parents is not None and parents.value:
            return 1.3
        return 0.5

    if field == "buyer_commute":
        return 1.2 if "office_location" in constraints else 0.8

    if field in ("floor_preference", "builder_preference"):
        return 0.6  # nice-to-have, deprioritized until the bigger fields are settled

    return 1.0


def uncertainty(field: str, profile: BuyerProfile) -> float:
    """1.0 for a fully unknown field; otherwise 1 - confidence, floored so an
    already-answered-but-ambiguous field can still be re-asked / refined.
    """
    c = profile.constraints.get(field)
    if c is None:
        return 1.0
    return round(max(0.05, 1.0 - c.confidence), 2)


def is_askable(field: str, profile: BuyerProfile) -> bool:
    """A field is worth asking about if it's unknown, has low confidence, or
    (for a range like budget) is still wide relative to its own size.
    """
    c = profile.constraints.get(field)
    if c is None:
        return True
    if c.confidence < CONFIDENCE_THRESHOLD:
        return True
    if c.min is not None and c.max is not None and c.min != c.max:
        span = c.max - c.min
        relative_spread = span / max(abs(c.max), 1)
        if relative_spread > RANGE_SPREAD_THRESHOLD:
            return True
    return False


def question_score(field: str, profile: BuyerProfile, candidates: list[dict]) -> tuple[float, float]:
    """Returns (score, expected_filter_strength) for one field."""
    strength = expected_filter_strength(field, candidates)
    relevance = buyer_relevance(field, profile)
    unc = uncertainty(field, profile)
    priority = PRIORITY_WEIGHTS.get(field, 0.5)
    return strength * relevance * unc * priority, strength


class QuestionScorer(Protocol):
    """Interface so the heuristic above can later be swapped for a more
    rigorous algorithm (e.g. true expected information gain over a
    probabilistic buyer-preference model) without touching policy.py.
    """

    def __call__(self, field: str, profile: BuyerProfile, candidates: list[dict]) -> tuple[float, float]: ...
