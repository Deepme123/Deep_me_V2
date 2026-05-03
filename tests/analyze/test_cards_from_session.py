import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

cards = importlib.import_module("app.analyze.routers.cards")
sc = importlib.import_module("app.analyze.schemas")
emotion_models = importlib.import_module("app.backend.models.emotion")


class FakeExecResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, sessions, steps_by_session):
        self.sessions = sessions
        self.steps_by_session = steps_by_session
        self.cards = []
        self._active_session_id = None

    def get(self, model, pk):
        model_name = getattr(model, "__name__", "")
        if model_name == "EmotionSession":
            self._active_session_id = pk
            return self.sessions.get(pk)
        return None

    def exec(self, _stmt):
        return FakeExecResult(self.steps_by_session.get(self._active_session_id, []))

    def add(self, obj):
        if getattr(obj, "__class__", type(obj)).__name__ == "AnalysisCard":
            self.cards.append(obj)

    def commit(self):
        return None

    def refresh(self, _obj):
        return None


def _build_client(fake_db):
    app = FastAPI()
    app.include_router(cards.router)
    app.dependency_overrides[cards.get_db] = lambda: fake_db
    return TestClient(app)


def _step(session_id, order, step_type, user_input="", gpt_response=""):
    return emotion_models.EmotionStep(
        session_id=session_id,
        step_order=order,
        step_type=step_type,
        user_input=user_input,
        gpt_response=gpt_response,
    )


def test_auto_from_session_creates_card_for_valid_session(monkeypatch):
    session_id = uuid4()
    fake_db = FakeDB(
        sessions={session_id: SimpleNamespace(session_id=session_id)},
        steps_by_session={
            session_id: [
                _step(session_id, 1, "user", user_input="요즘 계속 불안해요"),
                _step(session_id, 2, "assistant", gpt_response="어떤 순간에 가장 크게 느껴지나요?"),
            ]
        },
    )
    captured = {}

    def fake_analyze_dialogue_to_card(*, turns, title_hint):
        captured["turns"] = turns
        captured["title_hint"] = title_hint
        return sc.CardCreate(
            summary="불안 패턴 요약",
            emotion="불안",
            thoughts="같은 걱정을 반복함",
        )

    monkeypatch.setattr(cards, "analyze_dialogue_to_card", fake_analyze_dialogue_to_card)
    client = _build_client(fake_db)

    response = client.post(
        f"/api/sessions/{session_id}/cards/auto-from-session",
        json={"title_hint": "불안 패턴 정리"},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == str(session_id)
    assert response.json()["summary"] == "불안 패턴 요약"
    assert len(fake_db.cards) == 1
    assert captured["title_hint"] == "불안 패턴 정리"
    assert [(turn.role, turn.text) for turn in captured["turns"]] == [
        ("user", "요즘 계속 불안해요"),
        ("assistant", "어떤 순간에 가장 크게 느껴지나요?"),
    ]


def test_auto_from_session_returns_400_for_empty_or_non_dialogue_session(monkeypatch):
    session_id = uuid4()
    fake_db = FakeDB(
        sessions={session_id: SimpleNamespace(session_id=session_id)},
        steps_by_session={
            session_id: [
                _step(session_id, 1, "activity"),
            ]
        },
    )

    def fail_if_called(**_kwargs):
        raise AssertionError("analyze_dialogue_to_card should not be called for empty history")

    monkeypatch.setattr(cards, "analyze_dialogue_to_card", fail_if_called)
    client = _build_client(fake_db)

    response = client.post(f"/api/sessions/{session_id}/cards/auto-from-session")

    assert response.status_code == 400
    assert response.json()["detail"] == "conversation history is empty"
    assert fake_db.cards == []


def test_auto_from_session_returns_502_for_empty_generated_card(monkeypatch):
    session_id = uuid4()
    fake_db = FakeDB(
        sessions={session_id: SimpleNamespace(session_id=session_id)},
        steps_by_session={
            session_id: [
                _step(session_id, 1, "user", user_input="요즘 계속 불안해요"),
                _step(session_id, 2, "assistant", gpt_response="어떤 순간에 가장 크게 느껴지나요?"),
            ]
        },
    )

    monkeypatch.setattr(cards, "analyze_dialogue_to_card", lambda **_kwargs: sc.CardCreate())
    client = _build_client(fake_db)

    response = client.post(f"/api/sessions/{session_id}/cards/auto-from-session")

    assert response.status_code == 502
    assert response.json()["detail"] == "card generation failed"
    assert fake_db.cards == []


def test_auto_from_session_returns_404_for_missing_session(monkeypatch):
    session_id = uuid4()
    fake_db = FakeDB(sessions={}, steps_by_session={})

    def fail_if_called(**_kwargs):
        raise AssertionError("analyze_dialogue_to_card should not be called for missing session")

    monkeypatch.setattr(cards, "analyze_dialogue_to_card", fail_if_called)
    client = _build_client(fake_db)

    response = client.post(f"/api/sessions/{session_id}/cards/auto-from-session")

    assert response.status_code == 404
    assert response.json()["detail"] == "session not found"
    assert fake_db.cards == []


def test_auto_from_session_allows_multiple_cards_for_same_session(monkeypatch):
    session_id = uuid4()
    fake_db = FakeDB(
        sessions={session_id: SimpleNamespace(session_id=session_id)},
        steps_by_session={
            session_id: [
                _step(session_id, 1, "user", user_input="자꾸 같은 걱정이 떠올라요"),
                _step(session_id, 2, "assistant", gpt_response="그 걱정이 시작되는 장면을 떠올려볼까요?"),
            ]
        },
    )

    def fake_analyze_dialogue_to_card(*, turns, title_hint):
        return sc.CardCreate(
            summary=f"{title_hint or '기본'} 요약",
            emotion="걱정",
        )

    monkeypatch.setattr(cards, "analyze_dialogue_to_card", fake_analyze_dialogue_to_card)
    client = _build_client(fake_db)

    first = client.post(
        f"/api/sessions/{session_id}/cards/auto-from-session",
        json={"title_hint": "첫 번째"},
    )
    second = client.post(
        f"/api/sessions/{session_id}/cards/auto-from-session",
        json={"title_hint": "두 번째"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(fake_db.cards) == 2
    assert first.json()["card_id"] != second.json()["card_id"]
    assert first.json()["summary"] == "첫 번째 요약"
    assert second.json()["summary"] == "두 번째 요약"


def test_auto_from_session_uses_dialogue_transcript_only(monkeypatch):
    session_id = uuid4()
    fake_db = FakeDB(
        sessions={session_id: SimpleNamespace(session_id=session_id)},
        steps_by_session={
            session_id: [
                _step(session_id, 1, "user", user_input="I felt tense before the meeting."),
                _step(session_id, 2, "assistant", gpt_response="What part of the meeting felt hardest?"),
                _step(session_id, 3, "activity_suggest"),
                _step(session_id, 4, "cancel_close"),
                _step(session_id, 5, "user", user_input="My chest tightened when I had to speak."),
                _step(session_id, 6, "assistant", gpt_response="It sounds like the pressure showed up in your body, too."),
            ]
        },
    )
    captured = {}

    def fake_analyze_dialogue_to_card(*, turns, title_hint):
        captured["turns"] = turns
        return sc.CardCreate(
            summary="Meeting anxiety summary",
            emotion="anxiety",
        )

    monkeypatch.setattr(cards, "analyze_dialogue_to_card", fake_analyze_dialogue_to_card)
    client = _build_client(fake_db)

    response = client.post(f"/api/sessions/{session_id}/cards/auto-from-session")

    assert response.status_code == 200
    assert [(turn.role, turn.text) for turn in captured["turns"]] == [
        ("user", "I felt tense before the meeting."),
        ("assistant", "What part of the meeting felt hardest?"),
        ("user", "My chest tightened when I had to speak."),
        ("assistant", "It sounds like the pressure showed up in your body, too."),
    ]


def test_auto_from_session_ignores_marker_text_when_building_transcript(monkeypatch):
    session_id = uuid4()
    fake_db = FakeDB(
        sessions={session_id: SimpleNamespace(session_id=session_id)},
        steps_by_session={
            session_id: [
                _step(
                    session_id,
                    1,
                    "user",
                    user_input="The team meeting made me anxious.",
                ),
                _step(
                    session_id,
                    2,
                    "assistant",
                    gpt_response="What thought showed up right away?",
                ),
                _step(
                    session_id,
                    3,
                    "activity_suggest",
                    user_input="activity marker should never appear",
                    gpt_response="activity response should never appear",
                ),
                _step(
                    session_id,
                    4,
                    "cancel_close",
                    user_input="cancel_close marker should never appear",
                    gpt_response="cancel_close response should never appear",
                ),
                _step(
                    session_id,
                    5,
                    "user",
                    user_input="I thought I would freeze, my chest got tight, and I avoided eye contact.",
                ),
                _step(
                    session_id,
                    6,
                    "assistant",
                    gpt_response="You noticed fear, the thought of freezing, body tension, and avoidance.",
                ),
            ]
        },
    )
    captured = {}

    def fake_analyze_dialogue_to_card(*, turns, title_hint):
        captured["turns"] = turns
        return sc.CardCreate(
            summary="Meeting anxiety summary",
            situation="team meeting",
            emotion="anxiety",
            thoughts="I would freeze",
            physical_reactions=["tight chest"],
            behaviors="avoided eye contact",
        )

    monkeypatch.setattr(cards, "analyze_dialogue_to_card", fake_analyze_dialogue_to_card)
    client = _build_client(fake_db)

    response = client.post(f"/api/sessions/{session_id}/cards/auto-from-session")

    assert response.status_code == 200
    transcript_text = [turn.text for turn in captured["turns"]]
    assert transcript_text == [
        "The team meeting made me anxious.",
        "What thought showed up right away?",
        "I thought I would freeze, my chest got tight, and I avoided eye contact.",
        "You noticed fear, the thought of freezing, body tension, and avoidance.",
    ]
    assert "activity marker should never appear" not in "\n".join(transcript_text)
    assert "cancel_close marker should never appear" not in "\n".join(transcript_text)
