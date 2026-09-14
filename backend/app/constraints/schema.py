"""Data model for a buyer's evolving set of requirements.

`ConstraintValue` is deliberately generic (one shape for a city string, a
bedroom count, or a budget range) so `state.py` can apply one merge/update
algorithm to every field rather than special-casing each one.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ConstraintType = Literal["hard", "soft", "preference", "context"]

# The canonical set of fields the discovery engine knows how to ask about.
# `BuyerProfile.unknowns` is always this set minus whatever's already been
# established. Extraction (step 4) and discovery (step 5) both key off these
# names, so they're defined once, here.
TRACKED_FIELDS: list[str] = [
    "city",
    "bedrooms",
    "budget",
    "locality",
    "possession_date",
    "purpose",                 # self_use | investment
    "parents_living_with_buyer",
    "office_location",
    "hospital_access",         # priority: low | medium | high
    "buyer_commute",           # priority: low | medium | high
    "floor_preference",
    "parking",
    "builder_preference",
    "amenities",
]


class ConstraintValue(BaseModel):
    """One field of the buyer's profile.

    For scalar fields (city, bedrooms, a priority level) only `value` is
    used. For numeric-range fields (budget) `min`/`max` are used instead
    (an exact figure is represented as min == max). `previous` captures the
    prior state whenever a value actually changes, so corrections are never
    silently overwritten.
    """

    value: Any = None
    min: float | None = None
    max: float | None = None

    previous: Any = None       # snapshot of {value | (min, max)} before the last change
    changed: bool = False      # True if this field has ever been revised after its first set

    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    type: ConstraintType = "soft"

    source_turn: int = 0        # turn this field was first set on
    updated_at_turn: int = 0    # turn of the most recent update


class HistoryEntry(BaseModel):
    turn: int
    field: str
    old_value: Any
    new_value: Any
    reason: Literal["new_info", "correction", "refinement", "confirmation"]


class BuyerProfile(BaseModel):
    buyer_id: str
    constraints: dict[str, ConstraintValue] = Field(default_factory=dict)
    unknowns: list[str] = Field(default_factory=lambda: list(TRACKED_FIELDS))
    history: list[HistoryEntry] = Field(default_factory=list)
    turn_count: int = 0
