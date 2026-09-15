"""The per-turn pipeline: extraction -> state update -> search -> discovery
-> response. This is the core engine, deliberately voice-agnostic — it
takes and returns plain text/data, so it's fully testable without any
audio involved. Voice (a later step) is just another caller of
`process_utterance`.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.constraints.schema import BuyerProfile, HistoryEntry
from app.constraints.state import apply_constraint_update, begin_turn, create_profile
from app.conversation.responses import build_response
from app.conversation.search_bridge import build_search_criteria
from app.discovery.policy import DEFAULT_CONFIG, DiscoveryDecision, StoppingConfig, decide
from app.extraction.extractor import extract
from app.ranking.scorer import RankedProperty, rank_properties
from app.search.tools import search_properties


@dataclass
class TurnResult:
    turn: int
    applied: list[HistoryEntry]
    total_matches: int
    top_matches: list[RankedProperty]
    decision: DiscoveryDecision
    response_text: str


class ConversationManager:
    """Holds one buyer's evolving profile and question count across turns."""

    def __init__(self, buyer_id: str, stopping_config: StoppingConfig = DEFAULT_CONFIG):
        self.profile: BuyerProfile = create_profile(buyer_id)
        self.questions_asked = 0
        self.config = stopping_config
        # The field (and rendered text) the bot's last question was about, if
        # any. Threaded into extraction so a short, contextless reply like
        # "yes" / "nah" / "that works" can be resolved against the question
        # it's actually answering, instead of requiring the buyer to restate
        # the field's own keywords.
        self.pending_field: str | None = None
        self.pending_question_text: str | None = None

    def process_utterance(self, text: str, top_n: int = 5) -> TurnResult:
        turn = begin_turn(self.profile)

        updates = extract(text, self.profile, self.pending_field, self.pending_question_text)
        applied = [apply_constraint_update(self.profile, u, turn) for u in updates]

        criteria = build_search_criteria(self.profile)
        search_result = search_properties(criteria, limit=None)

        ranked = rank_properties(search_result.properties, self.profile)

        decision = decide(self.profile, search_result.properties, self.questions_asked, self.config)
        if not decision.should_stop:
            self.questions_asked += 1
            self.pending_field = decision.next_question.field
            self.pending_question_text = decision.next_question.question_text
        else:
            self.pending_field = None
            self.pending_question_text = None

        response_text = build_response(applied, decision, ranked)

        return TurnResult(
            turn=turn,
            applied=applied,
            total_matches=search_result.total_matches,
            top_matches=ranked[:top_n],
            decision=decision,
            response_text=response_text,
        )
