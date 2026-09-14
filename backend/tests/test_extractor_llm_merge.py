"""Tests the merge policy between rule-based and Gemini-sourced updates,
with Gemini mocked out (no real API calls in the test suite)."""
from app.constraints.state import create_profile
from app.extraction import extractor


def test_llm_updates_fill_gaps_rules_do_not_cover(monkeypatch):
    monkeypatch.setattr(extractor, "extract_constraints_llm", lambda utterance, summary: [
        {"field": "purpose", "value": "self_use", "confidence": 0.8, "type": "context"},
    ])
    profile = create_profile("demo-user")
    updates = {u.field: u for u in extractor.extract("some open-ended thing rules can't parse", profile)}
    assert updates["purpose"].value == "self_use"


def test_llm_never_overrides_a_rule_based_field(monkeypatch):
    monkeypatch.setattr(extractor, "extract_constraints_llm", lambda utterance, summary: [
        {"field": "bedrooms", "value": 4, "confidence": 0.9, "type": "hard"},
    ])
    profile = create_profile("demo-user")
    updates = {u.field: u for u in extractor.extract("I want a 3BHK", profile)}
    # Rule-based bedrooms=3 must win; the LLM's conflicting bedrooms=4 is dropped.
    assert updates["bedrooms"].value == 3


def test_llm_can_never_supply_budget_or_possession_date(monkeypatch):
    monkeypatch.setattr(extractor, "extract_constraints_llm", lambda utterance, summary: [
        {"field": "budget", "value": 99_000_000, "confidence": 0.9, "type": "soft"},
        {"field": "possession_date", "value": "2099-01", "confidence": 0.9, "type": "hard"},
    ])
    profile = create_profile("demo-user")
    updates = extractor.extract("some text with no numbers", profile)
    assert all(u.field not in ("budget", "possession_date") for u in updates)


def test_llm_updates_ignored_for_unknown_field(monkeypatch):
    monkeypatch.setattr(extractor, "extract_constraints_llm", lambda utterance, summary: [
        {"field": "not_a_real_field", "value": "x", "confidence": 0.9, "type": "context"},
    ])
    profile = create_profile("demo-user")
    updates = extractor.extract("irrelevant text", profile)
    assert updates == []
