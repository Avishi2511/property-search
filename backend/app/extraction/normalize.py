"""Deterministic parsing of Indian real-estate numbers and conversational dates.

This module never calls an LLM. Money and date values are exactly the kind
of thing the spec says must not be left entirely to LLM interpretation, so
every number/date that reaches a ConstraintUpdate has passed through here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

LAKH = 100_000
CRORE = 10_000_000

_WORD_DIGITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
}

_APPROX_WORDS = r"(?:around|about|roughly|approximately|nearly|say|maybe)"
_MAX_WORDS = r"(?:under|up\s*to|upto|maximum(?:\s+of)?|max(?:\s+of)?|not\s+more\s+than|within)"
_MIN_WORDS = r"(?:at\s+least|minimum(?:\s+of)?|min(?:\s+of)?|starting\s+from|more\s+than|over|above)"


@dataclass
class MoneyMention:
    value: float          # point estimate (midpoint for a range)
    min: float | None      # None if this is treated as an exact point value
    max: float | None
    approx: bool
    span: tuple[int, int]  # character offsets in the source text, for "last mention wins"


def _word_number_to_float(text: str) -> float | None:
    """Handles spoken numbers like 'one point eight' -> 1.8, 'two' -> 2."""
    tokens = text.lower().split()
    if not tokens:
        return None
    if "point" not in tokens:
        if len(tokens) == 1 and tokens[0] in _WORD_DIGITS:
            return float(_WORD_DIGITS[tokens[0]])
        return None
    idx = tokens.index("point")
    whole_tokens, decimal_tokens = tokens[:idx], tokens[idx + 1:]
    if len(whole_tokens) != 1 or whole_tokens[0] not in _WORD_DIGITS or not decimal_tokens:
        return None
    if any(t not in _WORD_DIGITS for t in decimal_tokens):
        return None
    whole = _WORD_DIGITS[whole_tokens[0]]
    decimal = "".join(str(_WORD_DIGITS[t]) for t in decimal_tokens)
    return float(f"{whole}.{decimal}")


_NUMERIC_RE = r"\d+(?:\.\d+)?"
_WORD_NUMBER_RE = (
    r"(?:zero|one|two|three|four|five|six|seven|eight|nine)"
    r"(?:\s+point\s+(?:zero|one|two|three|four|five|six|seven|eight|nine)+)?"
)
_UNIT_RE = r"crore|crores|cr|lakh|lakhs|lac|l"

_MONEY_RE = re.compile(
    rf"(?P<qualifier>{_APPROX_WORDS}|{_MAX_WORDS}|{_MIN_WORDS})?\s*"
    rf"₹?\s*(?:(?P<num>{_NUMERIC_RE})|(?P<word>{_WORD_NUMBER_RE}))\s*"
    rf"(?P<unit>{_UNIT_RE})\b",
    re.IGNORECASE,
)


def _unit_multiplier(unit: str) -> int:
    return CRORE if unit.lower() in ("crore", "crores", "cr") else LAKH


def find_money_mentions(text: str) -> list[MoneyMention]:
    """Finds every budget-like mention in `text`, in order of appearance."""
    mentions = []
    for m in _MONEY_RE.finditer(text):
        raw_num = m.group("num")
        value = float(raw_num) if raw_num else _word_number_to_float(m.group("word") or "")
        if value is None:
            continue
        amount = value * _unit_multiplier(m.group("unit"))

        qualifier = (m.group("qualifier") or "").lower().strip()
        is_approx = bool(re.fullmatch(_APPROX_WORDS, qualifier)) if qualifier else False
        is_max = bool(re.fullmatch(_MAX_WORDS, qualifier)) if qualifier else False
        is_min = bool(re.fullmatch(_MIN_WORDS, qualifier)) if qualifier else False

        if is_max:
            mentions.append(MoneyMention(value=amount, min=None, max=amount, approx=False, span=m.span()))
        elif is_min:
            mentions.append(MoneyMention(value=amount, min=amount, max=None, approx=False, span=m.span()))
        elif is_approx:
            tolerance = amount * 0.1
            mentions.append(
                MoneyMention(value=amount, min=amount - tolerance, max=amount + tolerance, approx=True, span=m.span())
            )
        else:
            mentions.append(MoneyMention(value=amount, min=amount, max=amount, approx=False, span=m.span()))

    return mentions


HESITATION_MARKERS = ("maybe", "actually", "no,", "no wait", "hmm", "let's say", "let us say", "i mean")


def has_hesitation(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in HESITATION_MARKERS)


def money_confidence(mention: MoneyMention, *, hesitant: bool) -> float:
    """Point/exact figures are trusted most; approximations and mid-hesitation
    utterances get lower confidence so the discovery engine knows to treat
    the number as provisional rather than final.
    """
    base = 0.95 if not mention.approx else 0.75
    if hesitant:
        base -= 0.1
    return round(max(0.4, min(0.98, base)), 2)


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

MONTH_NAMES = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

# Approximate month Diwali falls in, by year — festival dates shift on the
# lunar calendar; this is deliberately coarse (good enough to anchor
# "before Diwali next year" style phrasing in a demo).
DIWALI_MONTH_BY_YEAR = {2026: 11, 2027: 10, 2028: 10, 2029: 10, 2030: 10}
DEFAULT_DIWALI_MONTH = 11


@dataclass
class DateMention:
    year_month: str        # "YYYY-MM"
    approx: bool
    confidence: float
    span: tuple[int, int]


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    y, m0 = divmod(total, 12)
    return y, m0 + 1


def find_date_mentions(text: str, reference: tuple[int, int] = (2026, 9)) -> list[DateMention]:
    """Finds possession-date-like mentions. Every result is normalized to a
    "YYYY-MM" upper bound (the point by which the buyer wants possession).
    """
    ref_year, ref_month = reference
    lowered = text.lower()
    mentions: list[DateMention] = []

    # "within N months" / "within a year" / "within six months"
    _qty_words = {
        "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    }
    qty_alt = "|".join(sorted(_qty_words.keys(), key=len, reverse=True) + [r"\d+"])
    for m in re.finditer(rf"within\s+({qty_alt})\s+(month|months|year|years)", lowered):
        qty_raw, unit = m.group(1), m.group(2)
        qty = _qty_words[qty_raw] if qty_raw in _qty_words else int(qty_raw)
        months = qty if "month" in unit else qty * 12
        y, mo = _add_months(ref_year, ref_month, months)
        mentions.append(DateMention(f"{y:04d}-{mo:02d}", approx=False, confidence=0.85, span=m.span()))

    # "before Diwali [this year|next year]" / "before Diwali"
    for m in re.finditer(r"before\s+diwali(?:\s+(this|next)\s+year)?", lowered):
        offset_word = m.group(1)
        year = ref_year + (1 if offset_word == "next" else 0)
        month = DIWALI_MONTH_BY_YEAR.get(year, DEFAULT_DIWALI_MONTH)
        mentions.append(DateMention(f"{year:04d}-{month:02d}", approx=True, confidence=0.7, span=m.span()))

    # "early/mid/late <year>"
    for m in re.finditer(r"(early|mid|late)\s+(\d{4})", lowered):
        part, year = m.group(1), int(m.group(2))
        month = {"early": 3, "mid": 6, "late": 10}[part]
        mentions.append(DateMention(f"{year:04d}-{month:02d}", approx=True, confidence=0.65, span=m.span()))

    # "before <Month> <year>" / "by <Month> <year>" / explicit "<Month> <year>"
    month_pattern = "|".join(sorted(MONTH_NAMES.keys(), key=len, reverse=True))
    for m in re.finditer(
        rf"(before|by|around|in)?\s*({month_pattern})\.?\s*(\d{{4}})?", lowered
    ):
        qualifier, month_name, year_str = m.group(1), m.group(2), m.group(3)
        month = MONTH_NAMES[month_name]
        if year_str:
            year = int(year_str)
        else:
            # No year given: assume the next occurrence of that month from the reference date.
            year = ref_year if month >= ref_month else ref_year + 1
        approx = qualifier == "around" or year_str is None
        confidence = 0.6 if approx else 0.85
        mentions.append(DateMention(f"{year:04d}-{month:02d}", approx=approx, confidence=confidence, span=m.span()))

    # Deduplicate overlapping spans (keep the first/most specific match), then sort by position.
    mentions.sort(key=lambda d: d.span[0])
    deduped: list[DateMention] = []
    last_end = -1
    for mention in mentions:
        if mention.span[0] >= last_end:
            deduped.append(mention)
            last_end = mention.span[1]
    return deduped


# ---------------------------------------------------------------------------
# Bedrooms
# ---------------------------------------------------------------------------

_BEDROOM_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
}

_BEDROOM_RE = re.compile(
    r"(\d)\s*[- ]?\s*bhk|\b(\d)[\s-]*(?:bed\s*room|bedroom)s?\b"
    r"|\b(one|two|three|four|five)\s*[- ]?\s*(?:bhk|bed\s*room|bedroom)s?\b",
    re.IGNORECASE,
)


def find_bedrooms(text: str) -> int | None:
    m = _BEDROOM_RE.search(text)
    if not m:
        return None
    if m.group(1):
        return int(m.group(1))
    if m.group(2):
        return int(m.group(2))
    if m.group(3):
        return _BEDROOM_WORD_NUMBERS[m.group(3).lower()]
    return None
