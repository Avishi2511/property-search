"""Tests for progressive question selection: scoring heuristics and the
select/stop policy built on top of them."""
import pytest

from app.constraints.state import ConstraintUpdate, apply_constraint_update, begin_turn, create_profile
from app.discovery.policy import DEFAULT_CONFIG, StoppingConfig, decide, select_next_question
from app.discovery.questions import render_question
from app.discovery.scorer import (
    buyer_relevance,
    expected_filter_strength,
    is_askable,
    uncertainty,
)


def _properties(**overrides_list):
    """Builds a tiny synthetic candidate set. Each kwarg is a list of values
    for that field, one per property; all other fields get a fixed default.
    """
    n = len(next(iter(overrides_list.values())))
    base = {
        "id": None, "location": "Whitefield", "city": "Bangalore", "price": 18_000_000,
        "bedrooms": 3, "possession": "2027-01", "builder": "Skyline Builders",
        "amenities": ["pool", "gym"],
    }
    props = []
    for i in range(n):
        p = dict(base)
        p["id"] = f"property_{i:03d}"
        for field, values in overrides_list.items():
            p[field] = values[i]
        props.append(p)
    return props


# --- scorer.expected_filter_strength -----------------------------------------

def test_filter_strength_zero_when_all_candidates_identical():
    candidates = _properties(location=["Whitefield"] * 10)
    assert expected_filter_strength("locality", candidates) == 0.0


def test_filter_strength_high_when_evenly_split():
    candidates = _properties(location=["Whitefield", "Koramangala"] * 5)
    assert expected_filter_strength("locality", candidates) > 0.9


def test_filter_strength_moderate_for_skewed_distribution():
    candidates = _properties(location=["Whitefield"] * 9 + ["Koramangala"])
    strength = expected_filter_strength("locality", candidates)
    assert 0.0 < strength < 0.9


def test_filter_strength_non_filterable_field_returns_base_constant():
    candidates = _properties(location=["Whitefield"] * 10)
    assert expected_filter_strength("hospital_access", candidates) == pytest.approx(0.15)


def test_filter_strength_price_uses_quantile_bins():
    varied_prices = [10_000_000 + i * 1_000_000 for i in range(10)]
    candidates = _properties(price=varied_prices)
    assert expected_filter_strength("budget", candidates) > 0.8


def test_filter_strength_zero_for_single_candidate():
    candidates = _properties(location=["Whitefield"])
    assert expected_filter_strength("locality", candidates) == 0.0


def test_filter_strength_parking_uses_amenity_membership():
    candidates = _properties(amenities=[["parking"], ["pool"]] * 5)
    assert expected_filter_strength("parking", candidates) > 0.9


# --- scorer.buyer_relevance ---------------------------------------------------

def test_hospital_access_relevance_boosted_when_parents_living_with_buyer():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="parents_living_with_buyer", value=True, type="context"), turn
    )
    assert buyer_relevance("hospital_access", profile) > buyer_relevance("hospital_access", create_profile("other"))


def test_buyer_commute_relevance_boosted_when_office_known():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(
        profile, ConstraintUpdate(field="office_location", value="Koramangala", type="context"), turn
    )
    baseline = create_profile("other")
    assert buyer_relevance("buyer_commute", profile) > buyer_relevance("buyer_commute", baseline)


# --- scorer.uncertainty / is_askable ------------------------------------------

def test_uncertainty_full_for_unknown_field():
    profile = create_profile("demo-user")
    assert uncertainty("locality", profile) == 1.0


def test_uncertainty_reflects_confidence():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(profile, ConstraintUpdate(field="locality", value="Whitefield", confidence=0.7), turn)
    assert uncertainty("locality", profile) == pytest.approx(0.3)


def test_is_askable_true_for_unknown_and_low_confidence_and_wide_range():
    profile = create_profile("demo-user")
    assert is_askable("locality", profile) is True

    turn = begin_turn(profile)
    apply_constraint_update(profile, ConstraintUpdate(field="locality", value="Whitefield", confidence=0.5), turn)
    assert is_askable("locality", profile) is True

    apply_constraint_update(
        profile, ConstraintUpdate(field="budget", min=15_000_000, max=25_000_000, confidence=0.9), turn
    )
    assert is_askable("budget", profile) is True


def test_is_askable_false_for_confident_narrow_value():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(profile, ConstraintUpdate(field="bedrooms", value=3, confidence=0.98, type="hard"), turn)
    assert is_askable("bedrooms", profile) is False


# --- questions.render_question -------------------------------------------------

def test_hospital_question_changes_wording_with_parents_context():
    plain_profile = create_profile("demo-user")
    default_text = render_question("hospital_access", plain_profile)

    parent_profile = create_profile("demo-user-2")
    turn = begin_turn(parent_profile)
    apply_constraint_update(
        parent_profile, ConstraintUpdate(field="parents_living_with_buyer", value=True), turn
    )
    contextual_text = render_question("hospital_access", parent_profile)

    assert default_text != contextual_text
    assert "parents" in contextual_text.lower()


# --- policy.select_next_question / decide -------------------------------------

def test_select_next_question_picks_highest_scoring_field():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    apply_constraint_update(profile, ConstraintUpdate(field="city", value="Bangalore", confidence=0.99, type="hard"), turn)
    apply_constraint_update(profile, ConstraintUpdate(field="bedrooms", value=3, confidence=0.98, type="hard"), turn)
    apply_constraint_update(profile, ConstraintUpdate(field="budget", value=18_000_000, confidence=0.95), turn)

    # Locality varies evenly across candidates; possession is identical everywhere.
    candidates = _properties(location=["Whitefield", "Koramangala"] * 10, possession=["2027-01"] * 20)
    selection = select_next_question(profile, candidates)
    assert selection is not None
    assert selection.field == "locality"
    assert selection.estimated_reduction_pct > 50


def test_select_next_question_none_when_no_candidates():
    profile = create_profile("demo-user")
    assert select_next_question(profile, []) is None


def test_decide_stops_when_candidate_count_at_or_below_threshold():
    profile = create_profile("demo-user")
    candidates = _properties(location=["Whitefield"] * 5)
    decision = decide(profile, candidates, questions_asked=1, config=StoppingConfig(max_strong_matches=6))
    assert decision.should_stop is True
    assert decision.next_question is None
    assert "5" in decision.stop_reason


def test_decide_stops_at_max_questions():
    profile = create_profile("demo-user")
    candidates = _properties(location=["Whitefield", "Koramangala"] * 10)
    decision = decide(profile, candidates, questions_asked=8, config=StoppingConfig(max_questions=8))
    assert decision.should_stop is True
    assert "maximum" in decision.stop_reason.lower()


def test_decide_continues_with_a_question_when_space_still_large():
    profile = create_profile("demo-user")
    candidates = _properties(location=["Whitefield", "Koramangala"] * 10)
    decision = decide(profile, candidates, questions_asked=0)
    assert decision.should_stop is False
    assert decision.next_question is not None
    assert decision.next_question.field in {"locality", "budget", "bedrooms", "possession_date"}


def test_decide_stop_reason_when_no_useful_question_remains():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    for field in ["city", "bedrooms", "budget", "locality", "possession_date", "purpose",
                  "parents_living_with_buyer", "office_location", "hospital_access",
                  "buyer_commute", "floor_preference", "parking", "builder_preference", "amenities"]:
        apply_constraint_update(profile, ConstraintUpdate(field=field, value="x", confidence=0.99, type="hard"), turn)

    # Large, perfectly uniform candidate set: nothing left to ask would help.
    candidates = _properties(location=["Whitefield"] * 20)
    decision = decide(profile, candidates, questions_asked=0, config=StoppingConfig(max_strong_matches=6))
    assert decision.should_stop is True
