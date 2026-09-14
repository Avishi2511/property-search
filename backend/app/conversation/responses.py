"""Templated (non-LLM) response generation.

Kept deliberately deterministic and testable: the response is built from
structured facts (what changed this turn, the discovery decision, the
ranked matches) rather than generated free-form. This also matches the
explainability requirement — nothing here is a hidden LLM judgment call.
"""
from __future__ import annotations

from app.constraints.schema import HistoryEntry
from app.discovery.policy import DiscoveryDecision
from app.ranking.scorer import RankedProperty


def format_price(price: float) -> str:
    if price >= 10_000_000:
        return f"₹{price / 10_000_000:.2f} Cr"
    return f"₹{price / 100_000:.1f} L"


def describe_property(ranked: RankedProperty) -> str:
    p = ranked.property
    return f"{p['project']} in {p['location']} — {format_price(p['price'])}, {p['bedrooms']} BHK, possession {p['possession']}"


def build_lead_in(applied_entries: list[HistoryEntry]) -> str:
    if not applied_entries:
        return ""
    corrections = [e for e in applied_entries if e.reason == "correction"]
    if corrections:
        fields = ", ".join(sorted({e.field.replace("_", " ") for e in corrections}))
        return f"Got it, updated your {fields}."
    return "Got it."


def build_stop_message(decision: DiscoveryDecision, ranked: list[RankedProperty]) -> str:
    top = ranked[:3]
    plural = "s" if decision.candidate_count != 1 else ""
    lines = [
        f"I've narrowed this down to {decision.candidate_count} strong option{plural}. "
        f"Let me walk you through the top match{'es' if len(top) != 1 else ''}:"
    ]
    for i, r in enumerate(top, start=1):
        lines.append(f"{i}. {describe_property(r)}")
    return "\n".join(lines)


def build_response(
    applied_entries: list[HistoryEntry],
    decision: DiscoveryDecision,
    ranked: list[RankedProperty],
) -> str:
    lead_in = build_lead_in(applied_entries)
    body = build_stop_message(decision, ranked) if decision.should_stop else decision.next_question.question_text
    return f"{lead_in} {body}".strip()
