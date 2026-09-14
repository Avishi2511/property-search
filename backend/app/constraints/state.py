"""Merge/update logic for a BuyerProfile.

The one entry point, `apply_constraint_update`, is used for every kind of
utterance: a brand-new fact, a reaffirmation, a correction ("actually,
1.8"), or a refinement. It never silently overwrites — every change is
recorded in `profile.history`, and the prior value is kept on the
constraint itself via `previous`/`changed`.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.constraints.schema import BuyerProfile, ConstraintType, ConstraintValue, HistoryEntry, TRACKED_FIELDS


class ConstraintUpdate(BaseModel):
    """What the extraction layer (step 4) produces for one field from one utterance."""

    field: str
    value: Any = None
    min: float | None = None
    max: float | None = None
    confidence: float = 1.0
    type: ConstraintType = "soft"
    is_correction: bool = False  # explicit self-correction signal ("actually", "I said X but...")


def create_profile(buyer_id: str) -> BuyerProfile:
    return BuyerProfile(buyer_id=buyer_id)


def begin_turn(profile: BuyerProfile) -> int:
    """Advances and returns the turn counter. Call once per user utterance."""
    profile.turn_count += 1
    return profile.turn_count


def _effective_repr(min_v: float | None, max_v: float | None, value: Any) -> Any:
    """The comparable/displayable representation of a constraint's current
    value: a {"min", "max"} dict for ranges, or the raw scalar otherwise.
    """
    if min_v is not None or max_v is not None:
        return {"min": min_v, "max": max_v}
    return value


def apply_constraint_update(profile: BuyerProfile, update: ConstraintUpdate, turn: int) -> HistoryEntry:
    field = update.field
    existing = profile.constraints.get(field)
    new_effective = _effective_repr(update.min, update.max, update.value)

    if existing is None:
        profile.constraints[field] = ConstraintValue(
            value=update.value,
            min=update.min,
            max=update.max,
            confidence=update.confidence,
            type=update.type,
            source_turn=turn,
            updated_at_turn=turn,
        )
        entry = HistoryEntry(turn=turn, field=field, old_value=None, new_value=new_effective, reason="new_info")

    else:
        old_effective = _effective_repr(existing.min, existing.max, existing.value)

        if old_effective == new_effective:
            # Same information restated: treat as reinforcement, not a change.
            existing.confidence = max(update.confidence, existing.confidence + (1 - existing.confidence) * 0.5)
            existing.updated_at_turn = turn
            entry = HistoryEntry(
                turn=turn, field=field, old_value=old_effective, new_value=new_effective, reason="confirmation"
            )
        else:
            existing.previous = old_effective
            existing.value = update.value
            existing.min = update.min
            existing.max = update.max
            existing.changed = True
            existing.confidence = update.confidence
            existing.type = update.type
            existing.updated_at_turn = turn
            reason: Literal["correction", "refinement"] = "correction" if update.is_correction else "refinement"
            entry = HistoryEntry(turn=turn, field=field, old_value=old_effective, new_value=new_effective, reason=reason)

    profile.history.append(entry)
    _recompute_unknowns(profile)
    return entry


def _recompute_unknowns(profile: BuyerProfile) -> None:
    profile.unknowns = [f for f in TRACKED_FIELDS if f not in profile.constraints]


def get_constraint(profile: BuyerProfile, field: str) -> ConstraintValue | None:
    return profile.constraints.get(field)


def hard_constraint_fields(profile: BuyerProfile) -> dict[str, ConstraintValue]:
    return {f: c for f, c in profile.constraints.items() if c.type == "hard"}
