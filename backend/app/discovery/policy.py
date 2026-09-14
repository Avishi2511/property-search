"""Ties scoring together into a decision: ask this question next, or stop
and present matches. Also produces the explainability payload the UI shows
("why did you ask that").
"""
from __future__ import annotations

from dataclasses import dataclass

from app.constraints.schema import TRACKED_FIELDS, BuyerProfile
from app.discovery.questions import render_question
from app.discovery.scorer import QuestionScorer, is_askable, question_score


@dataclass
class StoppingConfig:
    max_strong_matches: int = 6     # stop once the candidate set is this small or smaller
    max_questions: int = 8          # hard cap regardless of remaining uncertainty
    min_question_score: float = 0.02  # below this, no remaining question is worth asking


DEFAULT_CONFIG = StoppingConfig()


@dataclass
class QuestionSelection:
    field: str
    question_text: str
    score: float
    estimated_reduction_pct: int
    reason: str


@dataclass
class DiscoveryDecision:
    should_stop: bool
    next_question: QuestionSelection | None
    stop_reason: str | None
    candidate_count: int


def askable_fields(profile: BuyerProfile) -> list[str]:
    return [f for f in TRACKED_FIELDS if is_askable(f, profile)]


def _build_reason(field: str, strength: float, candidate_count: int) -> str:
    pct = round(strength * 100)
    field_label = field.replace("_", " ")
    if strength >= 0.4:
        return (
            f"{field_label.capitalize()} is currently unknown and is estimated to meaningfully "
            f"split the {candidate_count} remaining candidates (~{pct}% expected narrowing)."
        )
    if strength > 0:
        return (
            f"{field_label.capitalize()} would only modestly narrow the {candidate_count} remaining "
            f"candidates (~{pct}%), but every other unknown would help even less right now."
        )
    return (
        f"{field_label.capitalize()} doesn't filter the remaining {candidate_count} candidates directly, "
        f"but it materially affects how they should be ranked."
    )


def select_next_question(
    profile: BuyerProfile,
    candidates: list[dict],
    scorer: QuestionScorer = question_score,
) -> QuestionSelection | None:
    fields = askable_fields(profile)
    if not fields or not candidates:
        return None

    scored = [(field, *scorer(field, profile, candidates)) for field in fields]
    scored.sort(key=lambda row: row[1], reverse=True)
    best_field, best_score, best_strength = scored[0]

    if best_score < DEFAULT_CONFIG.min_question_score:
        return None

    return QuestionSelection(
        field=best_field,
        question_text=render_question(best_field, profile),
        score=round(best_score, 4),
        estimated_reduction_pct=round(best_strength * 100),
        reason=_build_reason(best_field, best_strength, len(candidates)),
    )


def decide(
    profile: BuyerProfile,
    candidates: list[dict],
    questions_asked: int,
    config: StoppingConfig = DEFAULT_CONFIG,
    scorer: QuestionScorer = question_score,
) -> DiscoveryDecision:
    candidate_count = len(candidates)

    if candidate_count <= config.max_strong_matches:
        return DiscoveryDecision(
            should_stop=True,
            next_question=None,
            stop_reason=f"Narrowed down to {candidate_count} strong matches.",
            candidate_count=candidate_count,
        )

    if questions_asked >= config.max_questions:
        return DiscoveryDecision(
            should_stop=True,
            next_question=None,
            stop_reason=f"Reached the maximum of {config.max_questions} questions.",
            candidate_count=candidate_count,
        )

    selection = select_next_question(profile, candidates, scorer)
    if selection is None:
        return DiscoveryDecision(
            should_stop=True,
            next_question=None,
            stop_reason="No remaining question would meaningfully narrow the search further.",
            candidate_count=candidate_count,
        )

    return DiscoveryDecision(
        should_stop=False,
        next_question=selection,
        stop_reason=None,
        candidate_count=candidate_count,
    )
