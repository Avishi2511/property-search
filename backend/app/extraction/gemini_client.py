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

_MODEL_NAME = "gemini-2.5-flash-lite"

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
            for hospital_access/buyer_commute use exactly one of "low", "medium", "high";
            for purpose use exactly one of "self_use", "investment" — no other spelling),
  "confidence": 0.0-1.0,
  "type": one of ["hard", "soft", "preference", "context"],
  "is_correction": true if the buyer is explicitly revising a prior statement
                    (e.g. "actually", "I said X but", "no, I meant"), else false
}

You may be told which question the bot just asked, and which field it's about. A
short, context-only reply ("yes", "nah", "that works", "doesn't matter to me",
"the second one", "sure, that's fine") means nothing on its own — it only makes
sense as an answer to that pending question. When you're given that context, resolve
such SHORT, otherwise-meaningless replies against the pending field (e.g. "yes"/"sure"
after "Do you need dedicated parking?" -> {"field": "parking", "value": true};
"doesn't matter" after a hospital-access/commute priority question -> "medium").

Do NOT apply this resolution to a full sentence that already states whose place/value
it is. "My wife's office is in Koramangala" names Koramangala as the office location —
that is true regardless of what the pending field was, even if the bot had just asked
about locality. Only fall back to the pending field when the utterance truly carries no
attribution of its own.

If the pending field is "budget" or "possession_date", do not answer it yourself even
from context — omit it, the deterministic system owns those two fields exclusively.

Only include fields the utterance actually gives evidence for. Return [] if there is
nothing to extract. Return ONLY the JSON array, no other text."""


def _get_model():
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(_MODEL_NAME, system_instruction=_SYSTEM_INSTRUCTION)


def extract_constraints_llm(
    utterance: str,
    profile_summary: dict,
    pending_field: str | None = None,
    pending_question_text: str | None = None,
) -> list[dict]:
    """Returns a list of raw update dicts (field/value/confidence/type/is_correction),
    or [] if Gemini is unavailable or the call fails.

    `pending_field`/`pending_question_text` describe the bot's just-asked
    question, if any -- needed to resolve short context-only replies like
    "yes" or "that works" that carry no meaning on their own.
    """
    if not settings.gemini_enabled:
        return []

    pending_context = (
        f"The bot's last question (still awaiting an answer): \"{pending_question_text}\" "
        f"(field: \"{pending_field}\")\n\n"
        if pending_field
        else ""
    )
    prompt = (
        f"Current known buyer profile (for context on corrections/references): "
        f"{json.dumps(profile_summary)}\n\n"
        f"{pending_context}"
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
