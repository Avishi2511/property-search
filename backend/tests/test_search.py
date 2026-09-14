"""Tests for the property dataset + search tools layer."""
import json
from pathlib import Path

import pytest

from app.properties.repository import get_repository
from app.search.filters import SearchCriteria
from app.search.geo import haversine_km
from app.search.tools import (
    calculate_commute,
    compare_properties,
    find_nearby_places,
    get_property,
    save_search,
    search_properties,
)


@pytest.fixture(autouse=True)
def clean_saved_searches(tmp_path, monkeypatch):
    """Redirect save_search's output file so tests don't mutate real data."""
    import app.search.tools as tools_module

    monkeypatch.setattr(tools_module, "SAVED_SEARCHES_PATH", tmp_path / "saved_searches.json")
    yield


def test_dataset_loads_and_has_expected_size():
    repo = get_repository()
    properties = repo.all()
    assert 300 <= len(properties) <= 1000
    sample = properties[0]
    for key in ["id", "project", "location", "city", "latitude", "longitude",
                "price", "bedrooms", "area_sqft", "possession", "builder",
                "amenities", "nearby"]:
        assert key in sample


def test_dataset_has_locality_variation():
    repo = get_repository()
    locations = {p["location"] for p in repo.all()}
    assert len(locations) >= 10


def test_search_properties_filters_by_city_and_bedrooms():
    result = search_properties(SearchCriteria(city="Bangalore", bedrooms=3), limit=None)
    assert result.total_matches > 0
    assert all(p["bedrooms"] == 3 for p in result.properties)


def test_search_properties_filters_by_budget_range():
    criteria = SearchCriteria(budget_min=15_000_000, budget_max=22_000_000)
    result = search_properties(criteria, limit=None)
    assert result.total_matches > 0
    assert all(15_000_000 <= p["price"] <= 22_000_000 for p in result.properties)


def test_search_properties_filters_by_possession_deadline():
    criteria = SearchCriteria(possession_before="2027-06")
    result = search_properties(criteria, limit=None)
    assert result.total_matches > 0
    assert all(p["possession"] <= "2027-06" for p in result.properties)


def test_search_properties_filters_by_required_amenities():
    criteria = SearchCriteria(required_amenities=["pool", "gym"])
    result = search_properties(criteria, limit=None)
    assert result.total_matches > 0
    for p in result.properties:
        assert "pool" in p["amenities"]
        assert "gym" in p["amenities"]


def test_search_properties_narrows_as_constraints_are_added():
    """Core progressive-discovery premise: more constraints -> smaller (or equal) space."""
    all_count = search_properties(SearchCriteria(), limit=None).total_matches
    city_count = search_properties(SearchCriteria(city="Bangalore", bedrooms=3), limit=None).total_matches
    tight_count = search_properties(
        SearchCriteria(city="Bangalore", bedrooms=3, budget_min=15_000_000, budget_max=20_000_000),
        limit=None,
    ).total_matches
    assert all_count >= city_count >= tight_count


def test_search_properties_respects_limit():
    result = search_properties(SearchCriteria(), limit=5)
    assert len(result.properties) == 5
    assert result.total_matches > 5


def test_get_property_found_and_missing():
    repo = get_repository()
    any_id = repo.all()[0]["id"]
    assert get_property(any_id) is not None
    assert get_property("does_not_exist") is None


def test_compare_properties():
    repo = get_repository()
    ids = [p["id"] for p in repo.all()[:3]]
    result = compare_properties(ids + ["does_not_exist"])
    assert len(result["properties"]) == 3
    assert result["missing_ids"] == ["does_not_exist"]
    assert set(result["comparison"]["price"].keys()) == set(ids)


def test_calculate_commute_zero_distance():
    result = calculate_commute(12.9352, 77.6245, 12.9352, 77.6245)
    assert result["distance_km"] == 0
    assert result["estimated_minutes"] == 0


def test_calculate_commute_known_distance():
    # Roughly 1 degree of latitude ~= 111km
    result = calculate_commute(12.0, 77.0, 13.0, 77.0)
    assert 100 <= result["distance_km"] <= 122
    assert result["estimated_minutes"] > 0


def test_haversine_symmetry():
    d1 = haversine_km(12.9352, 77.6245, 12.9719, 77.6412)
    d2 = haversine_km(12.9719, 77.6412, 12.9352, 77.6245)
    assert d1 == pytest.approx(d2)


def test_find_nearby_places_within_radius_and_sorted():
    # Center on a known locality (Koramangala) from the generator.
    results = find_nearby_places(12.9352, 77.6245, radius_km=5.0)
    assert len(results) > 0
    distances = [r["distance_km"] for r in results]
    assert distances == sorted(distances)
    assert all(d <= 5.0 for d in distances)


def test_find_nearby_places_category_filter():
    results = find_nearby_places(12.9352, 77.6245, category="hospital", radius_km=10.0)
    assert len(results) > 0
    assert all(r["category"] == "hospital" for r in results)


def test_save_search_persists_entry(tmp_path):
    import app.search.tools as tools_module

    criteria = SearchCriteria(city="Bangalore", bedrooms=3)
    entry = save_search("demo-user", criteria, total_matches=42)
    assert entry["buyer_id"] == "demo-user"
    assert entry["total_matches"] == 42

    saved = json.loads(tools_module.SAVED_SEARCHES_PATH.read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["criteria"]["city"] == "Bangalore"
