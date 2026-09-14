"""Tests for translating hard constraints into a SearchCriteria."""
from app.constraints.state import ConstraintUpdate, apply_constraint_update, begin_turn, create_profile
from app.conversation.search_bridge import build_search_criteria


def test_only_hard_constraints_become_filters():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(profile, ConstraintUpdate(field="city", value="Bangalore", type="hard"), turn)
    apply_constraint_update(profile, ConstraintUpdate(field="bedrooms", value=3, type="hard"), turn)
    apply_constraint_update(
        profile, ConstraintUpdate(field="budget", min=18_000_000, max=22_000_000, type="soft"), turn
    )
    criteria = build_search_criteria(profile)
    assert criteria.city == "Bangalore"
    assert criteria.bedrooms == 3
    assert criteria.budget_min is None and criteria.budget_max is None  # soft budget must not filter


def test_hard_possession_deadline_becomes_possession_before():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="possession_date", value="2028-01", type="hard"), turn
    )
    criteria = build_search_criteria(profile)
    assert criteria.possession_before == "2028-01"


def test_hard_locality_relaxation_becomes_distance_filter():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile,
        ConstraintUpdate(field="locality", value={"near": "Koramangala", "max_minutes": 45}, type="hard"),
        turn,
    )
    criteria = build_search_criteria(profile)
    assert criteria.max_distance_km is not None
    assert criteria.reference_lat is not None and criteria.reference_lng is not None


def test_hard_parking_and_amenities_become_required_amenities():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(profile, ConstraintUpdate(field="parking", value=True, type="hard"), turn)
    apply_constraint_update(profile, ConstraintUpdate(field="amenities", value=["pool"], type="hard"), turn)
    criteria = build_search_criteria(profile)
    assert set(criteria.required_amenities) == {"parking", "pool"}
