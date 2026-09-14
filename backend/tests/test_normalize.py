"""Tests for deterministic money/date/bedroom parsing (no LLM involved)."""
import pytest

from app.extraction.normalize import (
    find_bedrooms,
    find_date_mentions,
    find_money_mentions,
    has_hesitation,
    money_confidence,
)


@pytest.mark.parametrize(
    "text,expected_amount",
    [
        ("2 crore", 20_000_000),
        ("₹2 crore", 20_000_000),
        ("2 Cr", 20_000_000),
        ("1.75 crore", 17_500_000),
        ("1.8 cr", 18_000_000),
        ("50 lakh", 5_000_000),
        ("50L", 5_000_000),
    ],
)
def test_money_exact_amounts(text, expected_amount):
    mentions = find_money_mentions(text)
    assert len(mentions) == 1
    assert mentions[0].value == expected_amount
    assert mentions[0].min == expected_amount
    assert mentions[0].max == expected_amount
    assert mentions[0].approx is False


def test_money_word_number():
    mentions = find_money_mentions("one point eight crore")
    assert len(mentions) == 1
    assert mentions[0].value == 18_000_000


def test_money_around_produces_range():
    mentions = find_money_mentions("around 2 crore")
    assert len(mentions) == 1
    m = mentions[0]
    assert m.approx is True
    assert m.min < 20_000_000 < m.max


def test_money_under_produces_max_only():
    mentions = find_money_mentions("under 2 crore")
    assert len(mentions) == 1
    m = mentions[0]
    assert m.max == 20_000_000
    assert m.min is None


def test_money_up_to_produces_max_only():
    mentions = find_money_mentions("up to 2.2 crore")
    assert len(mentions) == 1
    assert mentions[0].max == 22_000_000


def test_money_multiple_mentions_in_order():
    mentions = find_money_mentions("I can spend around 1.8 crore, maybe 2.1 crore if it's really worth it")
    assert len(mentions) == 2
    assert mentions[0].value == 18_000_000
    assert mentions[1].value == 21_000_000
    # "last mention wins" is a decision for the extractor; normalize just orders them
    assert mentions[0].span[0] < mentions[1].span[0]


def test_hesitation_detection():
    assert has_hesitation("Maybe around... 1.8? Yeah, 1.8 crore.")
    assert not has_hesitation("I want a 3BHK in Bangalore around two crore is wrong here")


def test_money_confidence_lower_for_approx_and_hesitant():
    exact = find_money_mentions("2 crore")[0]
    approx = find_money_mentions("around 2 crore")[0]
    assert money_confidence(exact, hesitant=False) > money_confidence(approx, hesitant=False)
    assert money_confidence(approx, hesitant=True) < money_confidence(approx, hesitant=False)


@pytest.mark.parametrize(
    "text,expected_bedrooms",
    [
        ("3BHK", 3),
        ("3 BHK", 3),
        ("three bedroom", 3),
        ("a 2-bedroom flat", 2),
        ("four bhk", 4),
    ],
)
def test_bedrooms_parsing(text, expected_bedrooms):
    assert find_bedrooms(text) == expected_bedrooms


def test_bedrooms_none_when_absent():
    assert find_bedrooms("I want something in Koramangala") is None


def test_date_within_months():
    mentions = find_date_mentions("I need possession within six months", reference=(2026, 9))
    assert len(mentions) == 1
    assert mentions[0].year_month == "2027-03"


def test_date_within_a_year():
    mentions = find_date_mentions("within a year", reference=(2026, 9))
    assert mentions[0].year_month == "2027-09"


def test_date_before_diwali_next_year():
    mentions = find_date_mentions("before Diwali next year", reference=(2026, 9))
    assert mentions[0].year_month == "2027-10"
    assert mentions[0].approx is True


def test_date_early_year():
    mentions = find_date_mentions("early 2028", reference=(2026, 9))
    assert mentions[0].year_month == "2028-03"


def test_date_around_month_infers_next_occurrence():
    # "around March" said in Sept 2026 should resolve to March 2027 (next occurrence)
    mentions = find_date_mentions("around March", reference=(2026, 9))
    assert mentions[0].year_month == "2027-03"
    assert mentions[0].approx is True


def test_date_explicit_month_year():
    mentions = find_date_mentions("before June 2028", reference=(2026, 9))
    assert mentions[0].year_month == "2028-06"
    assert mentions[0].approx is False


def test_date_in_n_months_phrasing():
    mentions = find_date_mentions("I need it in six months", reference=(2026, 9))
    assert len(mentions) == 1
    assert mentions[0].year_month == "2027-03"


def test_date_iso_style():
    mentions = find_date_mentions("possession by 2030-05", reference=(2026, 9))
    assert any(m.year_month == "2030-05" for m in mentions)


def test_date_bare_year_is_approximate_and_low_confidence():
    mentions = find_date_mentions("maybe around 2030", reference=(2026, 9))
    assert len(mentions) == 1
    assert mentions[0].year_month == "2030-12"
    assert mentions[0].approx is True
    assert mentions[0].confidence < 0.6


def test_date_maybe_not_misread_as_month_may():
    """Regression: 'maybe' contains 'may' as a substring; the month matcher
    must not fire on it without a word boundary."""
    mentions = find_date_mentions("maybe around 2030", reference=(2026, 9))
    assert len(mentions) == 1
    assert mentions[0].year_month == "2030-12"


def test_date_bare_year_suppressed_when_part_of_explicit_month_year():
    """A bare-year match inside 'before June 2028' must not also produce a
    separate, lower-confidence Dec-2028 mention."""
    mentions = find_date_mentions("before June 2028", reference=(2026, 9))
    assert len(mentions) == 1
    assert mentions[0].year_month == "2028-06"
