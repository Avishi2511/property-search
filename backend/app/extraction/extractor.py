"""Orchestrates constraint extraction from one utterance.

Pipeline: deterministic rules first (money, dates, bedrooms, locality,
common phrasing patterns) → Gemini fills in whatever the rules didn't
cover, for open-ended fields only. Money and dates are never taken from
Gemini, even if the rules found nothing — that's a deliberate choice per
the project's numeric-safety requirement, not an oversight.
"""
from __future__ import annotations

import re

from app.constraints.schema import BuyerProfile, TRACKED_FIELDS, ConstraintType
from app.constraints.state import ConstraintUpdate
from app.extraction.gemini_client import extract_constraints_llm
from app.extraction.normalize import (
    find_bedrooms,
    find_date_mentions,
    find_money_mentions,
    has_hesitation,
    money_confidence,
)
from app.properties.localities import LOCALITY_NAMES

_NEVER_FROM_LLM = {"budget", "possession_date"}

_CORRECTION_RE = re.compile(
    r"\bactually\b|\bi said\b.*\bbut\b|\binstead\b|\bno,? i meant\b|\bi mean\b|\bmake that\b|\bchange that\b",
    re.IGNORECASE,
)

_CITY_RE = re.compile(r"\bbangalore\b|\bbengaluru\b", re.IGNORECASE)

_PURPOSE_SELF_RE = re.compile(r"for myself|self.?use|to live in|for my own|for us to live", re.IGNORECASE)
_PURPOSE_INVESTMENT_RE = re.compile(r"\binvestment\b|rent it out|as an investment|to rent out", re.IGNORECASE)

_PARENTS_RE = re.compile(
    r"(?:my |our )?parents\b.*?(?:will|would|also)?\s*(?:stay|live|move in)"
    r"|(?:stay|live|move in)\s+with\s+(?:us|me).*?parents"
    r"|parents will (?:also )?(?:stay|live)",
    re.IGNORECASE,
)

_OFFICE_RE = re.compile(
    r"(?:my |wife'?s|husband'?s|spouse'?s|partner'?s)?\s*office\s+(?:is\s+)?(?:located\s+)?in\s+([A-Za-z][A-Za-z\s]{2,30})",
    re.IGNORECASE,
)

_WITHIN_MINUTES_OF_RE = re.compile(
    r"within\s+(\d+)\s*min(?:ute)?s?\s+of\s+([A-Za-z][A-Za-z\s]{2,30})", re.IGNORECASE
)

_HOSPITAL_HIGH_RE = re.compile(r"close to (?:a |the )?hospital|hospital access|near (?:a |the )?hospital", re.IGNORECASE)
_COMMUTE_LOW_RE = re.compile(r"commute (?:doesn'?t|does not|isn'?t) (?:matter|important)|commute.{0,15}less important", re.IGNORECASE)
_COMMUTE_HIGH_RE = re.compile(r"close to (?:my |the )?office|short commute|commute matters", re.IGNORECASE)
_HOSPITAL_OVER_COMMUTE_RE = re.compile(
    r"hospitals?.{0,20}(?:more important|priority).{0,20}(?:than).{0,20}commute", re.IGNORECASE
)

_PARKING_YES_RE = re.compile(
    r"need(?:s)?\s+(?:a\s+|dedicated\s+)?parking|with parking|parking is (?:a must|important|needed)",
    re.IGNORECASE,
)
_PARKING_NO_RE = re.compile(r"don'?t need parking|no parking needed|parking (?:doesn'?t|isn'?t) matter", re.IGNORECASE)

_AMENITY_KEYWORDS = {
    "pool": ["pool", "swimming pool"],
    "gym": ["gym", "fitness center", "fitness centre"],
    "clubhouse": ["clubhouse", "club house"],
    "park": ["park", "garden"],
    "jogging_track": ["jogging track", "walking track"],
    "children_play_area": ["kids play area", "children's play area", "play area"],
    "co_working_space": ["co-working", "coworking"],
}

_FLOOR_HIGH_RE = re.compile(r"higher floor|top floor|upper floor", re.IGNORECASE)
_FLOOR_LOW_RE = re.compile(r"lower floor|ground floor|lower floors", re.IGNORECASE)

_VALID_TYPES = {"hard", "soft", "preference", "context"}

# Fields where the bot's question is genuinely yes/no-shaped, so a bare
# affirmative/negative reply can be resolved with no keyword restatement at
# all -- but only when we know that's the field being answered (pending_field).
_BOOLEAN_FIELDS = {"parking", "parents_living_with_buyer"}

_AFFIRMATIVE_WORD = r"(?:yes|yeah|yep|yup|sure|of course|definitely|absolutely|correct|right)"
_NEGATIVE_WORD = (
    r"(?:no|nope|nah|not really|don'?t need (?:it|that|one)|do not need (?:it|that|one)|"
    r"no need|not needed)"
)
_AFFIRMATIVE_RE = re.compile(
    rf"^\s*{_AFFIRMATIVE_WORD}(?:[\s,.!]+{_AFFIRMATIVE_WORD})*[\s,.!]*$", re.IGNORECASE
)
_NEGATIVE_RE = re.compile(rf"^\s*{_NEGATIVE_WORD}(?:[\s,.!]+{_NEGATIVE_WORD})*[\s,.!]*$", re.IGNORECASE)


def _match_locality(text: str) -> str | None:
    lowered = text.lower()
    for name in LOCALITY_NAMES:
        if name.lower() in lowered:
            return name
    return None


def profile_summary(profile: BuyerProfile) -> dict:
    """Compact {field: value} view of the profile, for Gemini's context window."""
    return {field: c.value if c.value is not None else {"min": c.min, "max": c.max}
            for field, c in profile.constraints.items()}


def _rule_based_updates(
    utterance: str, profile: BuyerProfile, pending_field: str | None = None
) -> list[ConstraintUpdate]:
    updates: list[ConstraintUpdate] = []
    lowered = utterance.lower()
    is_correction = bool(_CORRECTION_RE.search(utterance))
    hesitant = has_hesitation(utterance)

    if _CITY_RE.search(utterance):
        updates.append(ConstraintUpdate(field="city", value="Bangalore", confidence=0.97, type="hard",
                                         is_correction=is_correction))

    bedrooms = find_bedrooms(utterance)
    if bedrooms is not None:
        updates.append(ConstraintUpdate(field="bedrooms", value=bedrooms, confidence=0.95, type="hard",
                                         is_correction=is_correction))

    money_mentions = find_money_mentions(utterance)
    if money_mentions:
        # Multiple mentions in one utterance = self-correction/hesitation mid-sentence;
        # the last one stated is what the buyer settled on.
        mention = money_mentions[-1]
        confidence = money_confidence(mention, hesitant=hesitant)
        exact = (not mention.approx) and mention.min == mention.max
        if exact:
            updates.append(ConstraintUpdate(field="budget", value=mention.value, confidence=confidence,
                                             type="soft", is_correction=is_correction or len(money_mentions) > 1))
        else:
            updates.append(ConstraintUpdate(field="budget", min=mention.min, max=mention.max, confidence=confidence,
                                             type="soft", is_correction=is_correction or len(money_mentions) > 1))

    date_mentions = find_date_mentions(utterance)
    if date_mentions:
        mention = date_mentions[-1]
        updates.append(ConstraintUpdate(field="possession_date", value=mention.year_month,
                                         confidence=mention.confidence,
                                         type="soft" if mention.approx else "hard",
                                         is_correction=is_correction))

    # Resolve office-location mentions first so a place named only as "my
    # wife's office is in X" isn't also picked up as the buyer's own
    # desired locality below.
    office_match = _OFFICE_RE.search(utterance)
    if office_match:
        raw_place = office_match.group(1).strip()
        canonical = _match_locality(raw_place) or raw_place.title()
        updates.append(ConstraintUpdate(field="office_location", value=canonical, confidence=0.88, type="context"))
        start, end = office_match.span(1)
        locality_search_text = utterance[:start] + " " + utterance[end:]
    else:
        locality_search_text = utterance

    within_match = _WITHIN_MINUTES_OF_RE.search(utterance)
    if within_match:
        minutes, place = int(within_match.group(1)), within_match.group(2).strip()
        canonical = _match_locality(place) or place.title()
        updates.append(ConstraintUpdate(
            field="locality", value={"near": canonical, "max_minutes": minutes},
            confidence=0.85, type="soft", is_correction=True,  # this phrasing is almost always a relaxation/correction
        ))
    else:
        locality = _match_locality(locality_search_text)
        if locality:
            updates.append(ConstraintUpdate(field="locality", value=locality, confidence=0.9, type="soft",
                                             is_correction=is_correction))

    if _PURPOSE_SELF_RE.search(utterance):
        updates.append(ConstraintUpdate(field="purpose", value="self_use", confidence=0.85, type="context"))
    elif _PURPOSE_INVESTMENT_RE.search(utterance):
        updates.append(ConstraintUpdate(field="purpose", value="investment", confidence=0.85, type="context"))

    if _PARENTS_RE.search(utterance):
        updates.append(ConstraintUpdate(field="parents_living_with_buyer", value=True, confidence=0.9, type="context"))

    if _HOSPITAL_OVER_COMMUTE_RE.search(utterance):
        updates.append(ConstraintUpdate(field="hospital_access", value="high", confidence=0.85, type="preference"))
        updates.append(ConstraintUpdate(field="buyer_commute", value="low", confidence=0.85, type="preference"))
    else:
        if _HOSPITAL_HIGH_RE.search(utterance):
            updates.append(ConstraintUpdate(field="hospital_access", value="high", confidence=0.8, type="preference"))
        if _COMMUTE_LOW_RE.search(utterance):
            updates.append(ConstraintUpdate(field="buyer_commute", value="low", confidence=0.8, type="preference"))
        elif _COMMUTE_HIGH_RE.search(utterance):
            updates.append(ConstraintUpdate(field="buyer_commute", value="high", confidence=0.8, type="preference"))

    if _PARKING_NO_RE.search(utterance):
        updates.append(ConstraintUpdate(field="parking", value=False, confidence=0.85, type="preference"))
    elif _PARKING_YES_RE.search(utterance):
        updates.append(ConstraintUpdate(field="parking", value=True, confidence=0.85, type="preference"))

    # A bare "yes"/"no" (or "yeah", "nope", "yes yes", ...) only means
    # anything in light of what was just asked -- it doesn't restate the
    # field's own keywords, so it can't be picked up by any of the
    # keyword-specific regexes above. Resolve it directly against
    # `pending_field` when that field is yes/no-shaped and nothing more
    # specific already matched it this turn.
    if (
        pending_field in _BOOLEAN_FIELDS
        and pending_field not in {u.field for u in updates}
    ):
        if _AFFIRMATIVE_RE.match(utterance):
            updates.append(ConstraintUpdate(field=pending_field, value=True, confidence=0.9, type="preference"))
        elif _NEGATIVE_RE.match(utterance):
            updates.append(ConstraintUpdate(field=pending_field, value=False, confidence=0.9, type="preference"))

    found_amenities = [
        canonical for canonical, keywords in _AMENITY_KEYWORDS.items()
        if any(re.search(rf"\b{re.escape(kw)}\b", lowered) for kw in keywords)
    ]
    if found_amenities:
        updates.append(ConstraintUpdate(field="amenities", value=found_amenities, confidence=0.85, type="preference"))

    if _FLOOR_HIGH_RE.search(utterance):
        updates.append(ConstraintUpdate(field="floor_preference", value="high", confidence=0.8, type="preference"))
    elif _FLOOR_LOW_RE.search(utterance):
        updates.append(ConstraintUpdate(field="floor_preference", value="low", confidence=0.8, type="preference"))

    return updates


def _llm_updates(
    utterance: str,
    profile: BuyerProfile,
    already_covered: set[str],
    pending_field: str | None,
    pending_question_text: str | None,
) -> list[ConstraintUpdate]:
    raw = extract_constraints_llm(
        utterance,
        profile_summary(profile),
        pending_field=pending_field,
        pending_question_text=pending_question_text,
    )
    updates = []
    for item in raw:
        field = item.get("field")
        if field not in TRACKED_FIELDS or field in _NEVER_FROM_LLM or field in already_covered:
            continue
        constraint_type: ConstraintType = item.get("type") if item.get("type") in _VALID_TYPES else "context"
        try:
            confidence = float(item.get("confidence", 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        confidence = max(0.0, min(1.0, confidence))
        updates.append(ConstraintUpdate(
            field=field,
            value=item.get("value"),
            confidence=confidence,
            type=constraint_type,
            is_correction=bool(item.get("is_correction", False)),
        ))
    return updates


def extract(
    utterance: str,
    profile: BuyerProfile,
    pending_field: str | None = None,
    pending_question_text: str | None = None,
) -> list[ConstraintUpdate]:
    """Returns the list of ConstraintUpdates found in `utterance`, ready to be
    applied via `apply_constraint_update` for each one.

    `pending_field`/`pending_question_text` describe the question the bot
    just asked (if any), so a short, contextless reply like "yes" or "that
    works" can be resolved against the field it's actually answering rather
    than requiring the buyer to restate the field's own keywords.
    """
    rule_updates = _rule_based_updates(utterance, profile, pending_field)
    covered_fields = {u.field for u in rule_updates}
    llm_updates = _llm_updates(utterance, profile, covered_fields, pending_field, pending_question_text)

    # Defense in depth: even with prompt guidance, a small/fast model can
    # still resolve a pending "locality" question onto a place this same
    # utterance already named as someone else's office (e.g. "my wife's
    # office is in Koramangala") — the exact office/locality conflation the
    # rule-based path guards against above. Deterministically drop an
    # LLM-sourced locality that duplicates this turn's own office_location.
    office_update = next((u for u in rule_updates if u.field == "office_location"), None)
    if office_update is not None:
        llm_updates = [
            u for u in llm_updates
            if not (u.field == "locality" and u.value == office_update.value)
        ]

    return rule_updates + llm_updates
