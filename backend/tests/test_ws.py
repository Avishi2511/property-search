"""Tests for the /ws/conversation WebSocket endpoint."""
import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ws_sends_init_message_with_total_property_count():
    with client.websocket_connect("/ws/conversation") as ws:
        init = json.loads(ws.receive_text())
        assert init["type"] == "init"
        assert init["search_space"]["total_matches"] > 0
        assert init["profile"]["constraints"] == {}
        assert len(init["profile"]["unknowns"]) > 0


def test_ws_processes_utterance_and_returns_turn_update():
    with client.websocket_connect("/ws/conversation") as ws:
        ws.receive_text()  # init
        ws.send_text(json.dumps({"type": "utterance", "text": "I want a 3BHK in Bangalore around two crore."}))
        turn = json.loads(ws.receive_text())

        assert turn["type"] == "turn_update"
        assert turn["profile"]["constraints"]["city"]["value"] == "Bangalore"
        assert turn["profile"]["constraints"]["bedrooms"]["value"] == 3
        assert turn["search_space"]["total_matches"] > 0
        assert len(turn["search_space"]["history"]) == 2  # initial total + this turn
        assert turn["discovery"]["should_stop"] in (True, False)
        assert turn["response_text"]


def test_ws_multi_turn_conversation_updates_state_progressively():
    with client.websocket_connect("/ws/conversation") as ws:
        ws.receive_text()  # init

        ws.send_text(json.dumps({"type": "utterance", "text": "My budget is 1.5 crore."}))
        first = json.loads(ws.receive_text())
        assert first["profile"]["constraints"]["budget"]["value"] == 15_000_000

        ws.send_text(json.dumps({"type": "utterance", "text": "Actually, I can stretch to 1.8 crore."}))
        second = json.loads(ws.receive_text())
        budget = second["profile"]["constraints"]["budget"]
        assert budget["value"] == 18_000_000
        assert budget["previous"] == 15_000_000
        assert budget["changed"] is True
        assert len(second["search_space"]["history"]) == 3


def test_ws_ignores_malformed_and_empty_messages():
    with client.websocket_connect("/ws/conversation") as ws:
        ws.receive_text()  # init
        ws.send_text("not json")
        ws.send_text(json.dumps({"type": "utterance", "text": "   "}))
        ws.send_text(json.dumps({"type": "utterance", "text": "3BHK"}))
        turn = json.loads(ws.receive_text())
        assert turn["type"] == "turn_update"
