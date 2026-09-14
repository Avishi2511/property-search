"""Thin wrapper around Gemini for open-ended constraint interpretation.

Used only for things the deterministic rules genuinely can't handle well:
purpose (self-use vs investment), priority framing ("hospital access matters
more than my commute"), free-form context ("wife's office is in X"),
correction/reference detection ("make that slightly higher"), and locality
phrasing that doesn't exactly match a known name.

Never used for money or date arithmetic — normalize.py owns that, and
extractor.py discards any numeric claim Gemini makes on its own.

If GEMINI_API_KEY isn't set, or the call fails for any reason, this returns
an empty list so the pipeline degrades to rule-based extraction only rather
than crashing a turn.
"""
from __future__ import annotations

import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)

_MODEL_NAME = "gemini-2.0-flash"

_SYSTEM_INSTRUCTION = """You extract structured real-estate buyer constraints from one \
spoken utterance in an ongoing conversation. You are a supporting signal, not the source \
of truth for numbers: another system already parses money and dates deterministically, so \
NEVER invent or restate a specific budget figure or date — omit those fields entirely and \
let the other system handle them.

Return a JSON array of updates. Each update is an object:
{
  "field": one of ["city", "bedrooms", "locality", "purpose", "parents_living_with_buyer",
                    "office_location", "hospital_access", "buyer_commute", "floor_preference",
                    "parking", "builder_preference", "amenities"],
  "value": the extracted value (string, number, boolean, or list of strings for amenities;
            for hospital_access/buyer_commute use one of "low", "medium", "high"),
  "confidence": 0.0-1.0,
  "type": one of ["hard", "soft", "preference", "context"],
  "is_correction": true if the buyer is explicitly revising a prior statement
                    (e.g. "actually", "I said X but", "no, I meant"), else false
}

Only include fields the utterance actually gives evidence for. Return [] if there is
nothing to extract. Return ONLY the JSON array, no other text."""


def _get_model():
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(_MODEL_NAME, system_instruction=_SYSTEM_INSTRUCTION)


def extract_constraints_llm(utterance: str, profile_summary: dict) -> list[dict]:
    """Returns a list of raw update dicts (field/value/confidence/type/is_correction),
    or [] if Gemini is unavailable or the call fails.
    """
    if not settings.gemini_enabled:
        return []

    prompt = (
        f"Current known buyer profile (for context on corrections/references): "
        f"{json.dumps(profile_summary)}\n\n"
        f"Buyer said: \"{utterance}\""
    )

    try:
        model = _get_model()
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.find("["):] if "[" in text else text
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, dict) and "field" in item]
    except Exception:
        logger.warning("Gemini extraction failed; falling back to rule-based only", exc_info=True)
        return []
