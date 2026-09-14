"""Realtime conversation endpoint.

One WebSocket connection = one buyer session = one ConversationManager
instance, kept alive in memory for the connection's lifetime. This is also
exactly the shape voice will plug into later: the browser will turn speech
into text turns and send them the same way; nothing here is voice-specific.
"""
from __future__ import annotations

import dataclasses
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.constraints.schema import BuyerProfile
from app.conversation.manager import ConversationManager, TurnResult
from app.properties.repository import get_repository

router = APIRouter()


def _serialize_profile(profile: BuyerProfile) -> dict:
    return {
        "buyer_id": profile.buyer_id,
        "constraints": {field: c.model_dump() for field, c in profile.constraints.items()},
        "unknowns": profile.unknowns,
        "turn_count": profile.turn_count,
    }


def _serialize_top_matches(top_matches) -> list[dict]:
    return [
        {
            "id": r.property["id"],
            "project": r.property["project"],
            "location": r.property["location"],
            "price": r.property["price"],
            "bedrooms": r.property["bedrooms"],
            "area_sqft": r.property["area_sqft"],
            "possession": r.property["possession"],
            "builder": r.property["builder"],
            "amenities": r.property["amenities"],
            "score": r.score,
            "breakdown": r.breakdown,
        }
        for r in top_matches
    ]


def _serialize_turn(manager: ConversationManager, result: TurnResult, search_history: list[int]) -> dict:
    return {
        "type": "turn_update",
        "turn": result.turn,
        "response_text": result.response_text,
        "profile": _serialize_profile(manager.profile),
        "search_space": {"total_matches": result.total_matches, "history": list(search_history)},
        "top_matches": _serialize_top_matches(result.top_matches),
        "discovery": dataclasses.asdict(result.decision),
        "applied_updates": [e.model_dump() for e in result.applied],
        "questions_asked": manager.questions_asked,
    }


@router.websocket("/ws/conversation")
async def conversation_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    manager = ConversationManager(buyer_id=f"buyer-{id(websocket)}")
    total_properties = len(get_repository().all())
    search_history = [total_properties]

    await websocket.send_text(json.dumps({
        "type": "init",
        "profile": _serialize_profile(manager.profile),
        "search_space": {"total_matches": total_properties, "history": search_history},
    }))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if message.get("type") != "utterance":
                continue
            text = (message.get("text") or "").strip()
            if not text:
                continue

            result = manager.process_utterance(text)
            search_history.append(result.total_matches)
            await websocket.send_text(json.dumps(_serialize_turn(manager, result, search_history)))
    except WebSocketDisconnect:
        pass
