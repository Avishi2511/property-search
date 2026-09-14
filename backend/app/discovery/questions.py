"""The bank of question candidates the discovery engine can choose from.

One template per trackable field. Most are static text; a couple render
differently depending on what's already known (e.g. the hospital-access
question changes wording once we know the buyer's parents are moving in
with them), matching the conversational examples in the spec.
"""
from __future__ import annotations

from typing import Callable

from app.constraints.schema import BuyerProfile

# Static weight expressing how important a field generally is to ask about,
# independent of the current candidate set. Hard/major constraints (budget,
# locality, bedrooms) outrank nice-to-haves (floor, builder).
PRIORITY_WEIGHTS: dict[str, float] = {
    "city": 0.4,                     # almost always already implied/known
    "bedrooms": 1.0,
    "budget": 1.0,
    "locality": 1.0,
    "possession_date": 0.9,
    "purpose": 0.6,
    "parents_living_with_buyer": 0.7,
    "office_location": 0.6,
    "hospital_access": 0.5,
    "buyer_commute": 0.5,
    "floor_preference": 0.3,
    "parking": 0.45,
    "builder_preference": 0.3,
    "amenities": 0.4,
}


def _render_hospital_access(profile: BuyerProfile) -> str:
    parents = profile.constraints.get("parents_living_with_buyer")
    if parents is not None and parents.value:
        return (
            "Since your parents will be staying with you, would access to hospitals "
            "and daily essentials be more important than keeping your own commute short?"
        )
    return "How important is being close to a hospital?"


def _render_buyer_commute(profile: BuyerProfile) -> str:
    office = profile.constraints.get("office_location")
    if office is not None and office.value:
        return f"How important is keeping your commute to {office.value} short?"
    return "How important is keeping your daily commute short?"


_STATIC_TEXT: dict[str, str] = {
    "city": "Which city are you looking to buy in?",
    "bedrooms": "How many bedrooms do you need?",
    "budget": "What's your budget range?",
    "locality": "What area do you need to be reasonably close to?",
    "possession_date": "When do you need possession by?",
    "purpose": "Is this mainly for you to live in, or are you considering it as an investment?",
    "parents_living_with_buyer": "Will anyone else, like your parents, be living with you?",
    "office_location": "Where is your (or your partner's) office located, so I can factor in commute?",
    "floor_preference": "Do you have a floor preference — higher or lower floors?",
    "parking": "Do you need dedicated parking?",
    "builder_preference": "Do you have a preferred builder in mind?",
    "amenities": "Are there any amenities that matter to you, like a pool or a gym?",
}

_DYNAMIC_RENDERERS: dict[str, Callable[[BuyerProfile], str]] = {
    "hospital_access": _render_hospital_access,
    "buyer_commute": _render_buyer_commute,
}


def render_question(field: str, profile: BuyerProfile) -> str:
    renderer = _DYNAMIC_RENDERERS.get(field)
    if renderer is not None:
        return renderer(profile)
    return _STATIC_TEXT.get(field, f"Can you tell me more about your {field.replace('_', ' ')} preference?")
