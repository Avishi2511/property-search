"""Tests for the rule-based extraction pipeline (extractor.py).

These run with no GEMINI_API_KEY set (see conftest.py), so extract() only
exercises the deterministic rules — which is exactly what should be
guaranteed to work correctly regardless of LLM availability.
"""
from app.constraints.state import apply_constraint_update, begin_turn, create_profile
from app.extraction.extractor import extract


def _updates_by_field(updates):
    return {u.field: u for u in updates}


def test_extract_basic_multi_constraint_utterance():
    profile = create_profile("demo-user")
    updates = _updates_by_field(extract("I want a 3BHK under 2 crore, preferably near a metro, and possession within a year", profile))
    assert updates["bedrooms"].value == 3
    assert updates["budget"].max == 20_000_000
    assert updates["budget"].min is None
    assert updates["possession_date"].value == "2027-09"  # relative to default reference (2026-09)


def test_extract_city_and_bedrooms_and_budget():
    profile = create_profile("demo-user")
    updates = _updates_by_field(extract("I want a 3BHK in Bangalore around 2 crore", profile))
    assert updates["city"].value == "Bangalore"
    assert updates["bedrooms"].value == 3
    budget = updates["budget"]
    assert budget.min < 20_000_000 < budget.max


def test_extract_out_of_order_information():
    profile = create_profile("demo-user")
    text = "Three bedrooms. My parents will stay with us. Budget is around two crore. Maybe Whitefield."
    updates = _updates_by_field(extract(text, profile))
    assert updates["bedrooms"].value == 3
    assert updates["parents_living_with_buyer"].value is True
    assert updates["locality"].value == "Whitefield"
    assert updates["budget"].min < 20_000_000 < updates["budget"].max


def test_extract_office_location():
    profile = create_profile("demo-user")
    updates = _updates_by_field(extract("My wife's office is in Koramangala", profile))
    assert updates["office_location"].value == "Koramangala"


def test_office_location_not_misread_as_buyer_locality():
    """Regression: mentioning a place only as someone else's office must not
    also set the buyer's own desired `locality` to that same place."""
    profile = create_profile("demo-user")
    updates = _updates_by_field(
        extract("My wife's office is in Koramangala, but my parents will live with us", profile)
    )
    assert updates["office_location"].value == "Koramangala"
    assert "locality" not in updates


def test_extract_hospital_over_commute_priority():
    profile = create_profile("demo-user")
    updates = _updates_by_field(
        extract("Being close to hospitals is more important than my commute", profile)
    )
    assert updates["hospital_access"].value == "high"
    assert updates["buyer_commute"].value == "low"


def test_extract_correction_locality():
    profile = create_profile("demo-user")
    turn = begin_turn(profile)
    for u in extract("I want Whitefield.", profile):
        apply_constraint_update(profile, u, turn)

    turn2 = begin_turn(profile)
    updates = extract("Actually, no, Koramangala.", profile)
    for u in updates:
        apply_constraint_update(profile, u, turn2)

    locality = profile.constraints["locality"]
    assert locality.value == "Koramangala"
    assert locality.previous == "Whitefield"
    assert locality.changed is True


def test_extract_within_minutes_of_relaxation():
    profile = create_profile("demo-user")
    updates = _updates_by_field(
        extract("I said Whitefield, but actually anywhere within 45 minutes of Koramangala works", profile)
    )
    locality = updates["locality"]
    assert locality.value == {"near": "Koramangala", "max_minutes": 45}
    assert locality.is_correction is True


def test_extract_budget_hesitation_last_value_wins():
    profile = create_profile("demo-user")
    updates = _updates_by_field(extract("Maybe around... 1.8... no, let's say 2 crore.", profile))
    budget = updates["budget"]
    # The buyer settled on 2 crore (the last figure stated) — the 1.8 mention,
    # having no unit of its own attached before the ellipsis, isn't parsed at all.
    settled_value = budget.value if budget.value is not None else budget.max
    assert 19_000_000 <= settled_value <= 22_500_000


def test_extract_contradiction_softens_without_deleting_context():
    profile = create_profile("demo-user")
    t1 = begin_turn(profile)
    for u in extract("I need to be close to my office", profile):
        apply_constraint_update(profile, u, t1)
    assert profile.constraints["buyer_commute"].value == "high"

    t2 = begin_turn(profile)
    for u in extract("Actually, my commute doesn't matter much", profile):
        apply_constraint_update(profile, u, t2)

    commute = profile.constraints["buyer_commute"]
    assert commute.value == "low"
    assert commute.previous == "high"


def test_extract_amenities():
    profile = create_profile("demo-user")
    updates = _updates_by_field(extract("A swimming pool and a gym would be nice", profile))
    assert set(updates["amenities"].value) == {"pool", "gym"}


def test_extract_amenities_does_not_false_positive_on_parking():
    """Regression: 'park' as an amenity keyword must not substring-match inside 'parking'."""
    profile = create_profile("demo-user")
    updates = _updates_by_field(extract("I need dedicated parking", profile))
    assert "amenities" not in updates
    assert updates["parking"].value is True


def test_extract_parking_with_intervening_word():
    profile = create_profile("demo-user")
    updates = _updates_by_field(extract("I need dedicated parking", profile))
    assert updates["parking"].value is True


def test_extract_no_matches_returns_empty_for_irrelevant_text():
    profile = create_profile("demo-user")
    updates = extract("Hello there, how are you?", profile)
    assert updates == []
