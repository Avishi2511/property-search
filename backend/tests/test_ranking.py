"""Tests for the deterministic ranking layer."""
import pytest

from app.constraints.state import ConstraintUpdate, apply_constraint_update, begin_turn, create_profile
from app.ranking.scorer import rank_properties, score_property


def _property(**overrides):
    base = {
        "id": "property_001", "location": "Whitefield", "city": "Bangalore",
        "latitude": 12.9698, "longitude": 77.7500, "price": 18_000_000, "bedrooms": 3,
        "area_sqft": 1500, "possession": "2027-01", "builder": "Skyline Builders",
        "amenities": ["pool", "gym"], "nearby": {"hospital": 2.0, "school": 1.5, "metro": 3.0},
    }
    base.update(overrides)
    return base


def test_no_known_soft_constraints_gives_neutral_score():
    profile = create_profile("demo-user")
    score, breakdown = score_property(_property(), profile)
    assert score == 50.0
    assert breakdown == {}


def test_budget_fit_prefers_closer_to_midpoint():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="budget", min=18_000_000, max=22_000_000, confidence=0.9), turn
    )
    near_mid_score, _ = score_property(_property(price=20_000_000), profile)
    edge_score, _ = score_property(_property(price=18_100_000), profile)
    assert near_mid_score >= edge_score


def test_budget_fit_penalizes_outside_range():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="budget", min=18_000_000, max=20_000_000, confidence=0.9), turn
    )
    in_range, _ = score_property(_property(price=19_000_000), profile)
    far_outside, _ = score_property(_property(price=35_000_000), profile)
    assert in_range > far_outside


def test_hard_bedroom_violation_excluded_from_ranking():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(profile, ConstraintUpdate(field="bedrooms", value=3, type="hard", confidence=0.98), turn)
    candidates = [_property(id="a", bedrooms=3), _property(id="b", bedrooms=2)]
    ranked = rank_properties(candidates, profile)
    assert [r.property["id"] for r in ranked] == ["a"]


def test_hard_budget_violation_excluded_from_ranking():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="budget", max=20_000_000, type="hard", confidence=0.95), turn
    )
    candidates = [_property(id="a", price=19_000_000), _property(id="b", price=30_000_000)]
    ranked = rank_properties(candidates, profile)
    assert [r.property["id"] for r in ranked] == ["a"]


def test_locality_exact_match_scores_higher_than_distant_locality():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(profile, ConstraintUpdate(field="locality", value="Whitefield", confidence=0.9), turn)
    matching, _ = score_property(_property(location="Whitefield"), profile)
    other, _ = score_property(_property(location="Devanahalli", latitude=13.2437, longitude=77.7139), profile)
    assert matching > other


def test_locality_relaxation_within_minutes_of():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile,
        ConstraintUpdate(field="locality", value={"near": "Koramangala", "max_minutes": 45}, confidence=0.85),
        turn,
    )
    close_prop = _property(latitude=12.9352, longitude=77.6245)   # Koramangala itself
    far_prop = _property(latitude=13.2437, longitude=77.7139)     # Devanahalli, far away
    close_score, _ = score_property(close_prop, profile)
    far_score, _ = score_property(far_prop, profile)
    assert close_score > far_score


def test_possession_before_deadline_scores_full():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="possession_date", value="2028-01", confidence=0.8), turn
    )
    on_time, _ = score_property(_property(possession="2027-06"), profile)
    late, _ = score_property(_property(possession="2029-06"), profile)
    assert on_time > late


def test_amenities_partial_match_scored_proportionally():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="amenities", value=["pool", "gym", "clubhouse"], confidence=0.85), turn
    )
    _, breakdown = score_property(_property(amenities=["pool", "gym"]), profile)
    assert breakdown["amenities"] == pytest.approx(2 / 3, rel=1e-2)


def test_parking_required_but_missing_scores_zero_on_that_factor():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(profile, ConstraintUpdate(field="parking", value=True, confidence=0.85), turn)
    _, breakdown = score_property(_property(amenities=["pool"]), profile)
    assert breakdown["parking"] == 0.0


def test_hospital_access_priority_scales_weight():
    profile_high = create_profile("demo-user-high")
    turn = begin_turn(profile_high)
    apply_constraint_update(
        profile_high, ConstraintUpdate(field="hospital_access", value="high", confidence=0.9), turn
    )
    close_prop = _property(nearby={"hospital": 0.5, "school": 1.0, "metro": 2.0})
    far_prop = _property(nearby={"hospital": 8.0, "school": 1.0, "metro": 2.0})
    close_score, _ = score_property(close_prop, profile_high)
    far_score, _ = score_property(far_prop, profile_high)
    assert close_score > far_score


def test_low_confidence_constraint_influences_score_less_than_high_confidence():
    low_conf_profile = create_profile("low")
    turn = begin_turn(low_conf_profile)
    apply_constraint_update(
        low_conf_profile, ConstraintUpdate(field="budget", min=18_000_000, max=20_000_000, confidence=0.3), turn
    )

    high_conf_profile = create_profile("high")
    turn2 = begin_turn(high_conf_profile)
    apply_constraint_update(
        high_conf_profile, ConstraintUpdate(field="budget", min=18_000_000, max=20_000_000, confidence=0.95), turn2
    )

    outside_budget_prop = _property(price=35_000_000)
    low_conf_score, _ = score_property(outside_budget_prop, low_conf_profile)
    high_conf_score, _ = score_property(outside_budget_prop, high_conf_profile)
    # The out-of-budget penalty should bite harder when we're confident about the budget.
    assert high_conf_score < low_conf_score


def test_ranking_is_deterministic_across_runs():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="budget", min=18_000_000, max=20_000_000, confidence=0.9), turn
    )
    candidates = [_property(id=f"p{i}", price=17_000_000 + i * 200_000) for i in range(10)]
    ranked1 = [r.property["id"] for r in rank_properties(candidates, profile)]
    ranked2 = [r.property["id"] for r in rank_properties(candidates, profile)]
    assert ranked1 == ranked2
