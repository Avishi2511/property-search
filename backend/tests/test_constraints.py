"""Tests for BuyerProfile state management: new facts, corrections, refinements,
confirmations, and the unknowns list."""
import pytest

from app.constraints.schema import TRACKED_FIELDS
from app.constraints.state import (
    ConstraintUpdate,
    apply_constraint_update,
    begin_turn,
    create_profile,
    get_constraint,
    hard_constraint_fields,
)


def test_new_profile_starts_with_all_fields_unknown():
    profile = create_profile("demo-user")
    assert set(profile.unknowns) == set(TRACKED_FIELDS)
    assert profile.constraints == {}
    assert profile.history == []


def test_setting_a_new_field_removes_it_from_unknowns():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="city", value="Bangalore", confidence=0.99, type="hard"), turn
    )
    assert "city" not in profile.unknowns
    assert get_constraint(profile, "city").value == "Bangalore"
    assert profile.history[-1].reason == "new_info"
    assert profile.history[-1].old_value is None


def test_budget_stored_as_range_for_ambiguous_statement():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile,
        ConstraintUpdate(field="budget", min=19_000_000, max=21_000_000, confidence=0.8, type="soft"),
        turn,
    )
    budget = get_constraint(profile, "budget")
    assert budget.min == 19_000_000
    assert budget.max == 21_000_000
    assert budget.value is None
    assert budget.changed is False


def test_budget_correction_preserves_history_and_marks_changed():
    """1.5Cr -> 1.8Cr: previous value must be preserved, not overwritten."""
    profile = create_profile("demo-user")
    t1 = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="budget", min=15_000_000, max=15_000_000, confidence=0.9, type="soft"), t1
    )

    t2 = begin_turn(profile)
    entry = apply_constraint_update(
        profile,
        ConstraintUpdate(
            field="budget", min=18_000_000, max=18_000_000, confidence=0.9, type="soft", is_correction=True
        ),
        t2,
    )

    budget = get_constraint(profile, "budget")
    assert budget.min == 18_000_000
    assert budget.max == 18_000_000
    assert budget.previous == {"min": 15_000_000, "max": 15_000_000}
    assert budget.changed is True
    assert entry.reason == "correction"


def test_budget_expansion_scalar_example_from_spec():
    """Mirrors the spec's example: current=21000000, previous=18000000, changed=true."""
    profile = create_profile("demo-user")
    t1 = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="budget", value=18_000_000, confidence=0.85, type="soft"), t1
    )

    t2 = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="budget", value=21_000_000, confidence=0.85, type="soft"), t2
    )

    budget = get_constraint(profile, "budget")
    assert budget.value == 21_000_000
    assert budget.previous == 18_000_000
    assert budget.changed is True


def test_location_correction_updates_rather_than_appends():
    """"I said Whitefield, but actually Koramangala" updates the field in place."""
    profile = create_profile("demo-user")
    t1 = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="locality", value="Whitefield", confidence=0.9, type="soft"), t1
    )
    t2 = begin_turn(profile)
    apply_constraint_update(
        profile,
        ConstraintUpdate(field="locality", value="Koramangala", confidence=0.9, type="soft", is_correction=True),
        t2,
    )
    locality = get_constraint(profile, "locality")
    assert locality.value == "Koramangala"
    assert locality.previous == "Whitefield"
    assert len(profile.constraints) == 1  # not appended as a second entry


def test_restating_same_value_is_a_confirmation_and_boosts_confidence():
    profile = create_profile("demo-user")
    t1 = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="bedrooms", value=3, confidence=0.6, type="hard"), t1
    )
    t2 = begin_turn(profile)
    entry = apply_constraint_update(
        profile, ConstraintUpdate(field="bedrooms", value=3, confidence=0.6, type="hard"), t2
    )
    bedrooms = get_constraint(profile, "bedrooms")
    assert bedrooms.changed is False
    assert bedrooms.confidence > 0.6
    assert entry.reason == "confirmation"


def test_priority_change_is_a_refinement_not_a_correction():
    """"commute doesn't matter much" after "close to office is important" —
    this updates a priority field's value, softening it, without deleting context."""
    profile = create_profile("demo-user")
    t1 = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="buyer_commute", value="high", confidence=0.8, type="preference"), t1
    )
    t2 = begin_turn(profile)
    entry = apply_constraint_update(
        profile, ConstraintUpdate(field="buyer_commute", value="low", confidence=0.8, type="preference"), t2
    )
    commute = get_constraint(profile, "buyer_commute")
    assert commute.value == "low"
    assert commute.previous == "high"
    assert entry.reason == "refinement"


def test_hard_constraint_fields_filters_by_type():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(profile, ConstraintUpdate(field="city", value="Bangalore", type="hard"), turn)
    apply_constraint_update(profile, ConstraintUpdate(field="amenities", value=["pool"], type="preference"), turn)
    hard = hard_constraint_fields(profile)
    assert list(hard.keys()) == ["city"]


def test_turn_counter_increments():
    profile = create_profile("demo-user")
    assert begin_turn(profile) == 1
    assert begin_turn(profile) == 2
    assert profile.turn_count == 2
