"""End-to-end tests for the full pipeline via ConversationManager, against
the real generated property dataset. This is the main integration test for
the "does the whole thing actually work together" question.
"""
from app.conversation.manager import ConversationManager
from app.discovery.policy import StoppingConfig


def test_first_utterance_extracts_and_narrows_search_space():
    manager = ConversationManager("demo-user")
    result = manager.process_utterance("I want a 3BHK in Bangalore around two crore.")

    assert manager.profile.constraints["city"].value == "Bangalore"
    assert manager.profile.constraints["bedrooms"].value == 3
    budget = manager.profile.constraints["budget"]
    assert budget.min < 20_000_000 < budget.max

    assert 0 < result.total_matches < 550  # narrowed from the full dataset
    assert result.decision.should_stop is False
    assert result.decision.next_question is not None
    assert result.response_text  # a question was asked


def test_conversation_narrows_search_space_progressively():
    manager = ConversationManager("demo-user")
    counts = []

    turns = [
        "I want a 3BHK in Bangalore around two crore.",
        "My wife's office is in Koramangala, but my parents will live with us, "
        "so being close to hospitals is more important than my commute.",
        "I'd like it in Whitefield.",
        "Possession before June 2028.",
    ]
    for text in turns:
        result = manager.process_utterance(text)
        counts.append(result.total_matches)

    # Progressive discovery premise: the hard-filtered space never grows.
    for earlier, later in zip(counts, counts[1:]):
        assert later <= earlier


def test_budget_correction_is_preserved_across_turns():
    manager = ConversationManager("demo-user")
    manager.process_utterance("My budget is 1.5 crore.")
    manager.process_utterance("Actually, I can stretch to 1.8 crore.")

    budget = manager.profile.constraints["budget"]
    assert budget.value == 18_000_000
    assert budget.previous == 15_000_000
    assert budget.changed is True


def test_conversation_eventually_stops_with_enough_hard_constraints():
    # A tight config + several specific constraints should converge quickly.
    manager = ConversationManager("demo-user", stopping_config=StoppingConfig(max_strong_matches=10, max_questions=6))
    manager.process_utterance("I want a 3BHK in Bangalore under 2 crore.")
    manager.process_utterance("Whitefield please.")
    result = manager.process_utterance("Possession before December 2027.")

    # Not asserting it stops on this exact turn (dataset-dependent), but it
    # must stop within the configured question budget.
    for _ in range(10):
        if result.decision.should_stop:
            break
        result = manager.process_utterance("I don't have any other preferences.")
    assert result.decision.should_stop is True
    assert "narrowed" in result.response_text.lower() or "reached" in (result.decision.stop_reason or "").lower()


def test_stop_message_lists_top_matches():
    manager = ConversationManager("demo-user", stopping_config=StoppingConfig(max_strong_matches=500))
    result = manager.process_utterance("I want a 3BHK in Bangalore.")
    assert result.decision.should_stop is True
    assert "1." in result.response_text
    assert "₹" in result.response_text


def test_out_of_order_information_all_captured():
    manager = ConversationManager("demo-user")
    manager.process_utterance(
        "Three bedrooms. My parents will stay with us. Budget is around two crore. Maybe Whitefield."
    )
    c = manager.profile.constraints
    assert c["bedrooms"].value == 3
    assert c["parents_living_with_buyer"].value is True
    assert c["locality"].value == "Whitefield"
    assert c["budget"].min < 20_000_000 < c["budget"].max


def test_response_acknowledges_correction():
    manager = ConversationManager("demo-user")
    manager.process_utterance("I want Whitefield.")
    result = manager.process_utterance("Actually, no, Koramangala.")
    assert "updated" in result.response_text.lower()
    assert manager.profile.constraints["locality"].value == "Koramangala"


def test_questions_asked_counter_increments_only_when_continuing():
    manager = ConversationManager("demo-user", stopping_config=StoppingConfig(max_strong_matches=500))
    manager.process_utterance("I want a 3BHK in Bangalore.")
    assert manager.questions_asked == 0  # should have stopped immediately (huge match count -> still, config forces stop)
