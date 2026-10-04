import asyncio
import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")
os.environ.setdefault("JWT_SECRET_KEY", "test-ws-recv-safe-secret")

import pytest
from fastapi import WebSocketDisconnect

from app.backend.services.ws_protocol import IdleTimeout, InvalidPayload, ws_recv_safe


class _FakeWebSocket:
    def __init__(self, event=None, *, error: Exception | None = None, hang: bool = False):
        self._event = event
        self._error = error
        self._hang = hang

    async def receive(self):
        if self._hang:
            await asyncio.sleep(10)
        if self._error is not None:
            raise self._error
        return self._event


def _recv(event=None, **kwargs):
    ws_kwargs = {k: kwargs.pop(k) for k in ("error", "hang") if k in kwargs}
    return asyncio.run(ws_recv_safe(_FakeWebSocket(event, **ws_kwargs), **kwargs))


def _text(text: str, **kwargs):
    return _recv({"type": "websocket.receive", "text": text}, **kwargs)


def test_json_object_with_type_is_returned_as_is():
    assert _text('{"type": "task_recommend", "max_items": 3, "extra": 1}') == {
        "type": "task_recommend",
        "max_items": 3,
        "extra": 1,
    }


def test_json_object_without_type_is_normalized_to_message():
    assert _text('{"text": "안녕", "topic": "일", "unknown": 1, "access_token": "t"}') == {
        "type": "message",
        "text": "안녕",
        "topic": "일",
        "access_token": "t",
    }


def test_user_input_takes_precedence_over_text():
    assert _text('{"user_input": "a", "text": "b"}') == {"type": "message", "text": "a"}
    assert _text('{"user_input": "", "text": "b"}') == {"type": "message", "text": "b"}
    assert _text('{"text": null}') == {"type": "message", "text": ""}


@pytest.mark.parametrize("raw", ['{"foo": 1}', "[1, 2]", '"just a string"'])
def test_json_without_type_or_text_falls_back_to_raw_message(raw):
    assert _text(raw) == {"type": "message", "text": raw}


def test_invalid_json_raises_when_strict():
    with pytest.raises(InvalidPayload, match="invalid_json"):
        _text("{not json")


def test_invalid_json_falls_back_to_raw_message_when_not_strict():
    assert _text("{not json", strict_json=False) == {"type": "message", "text": "{not json"}


@pytest.mark.parametrize("keyword", ["ping", "open", "close", "confirm_close", "cancel_close"])
def test_bare_keywords_are_case_and_whitespace_insensitive(keyword):
    assert _text(f"  {keyword.upper()}\n") == {"type": keyword}


@pytest.mark.parametrize("word", ["message", "task_recommend", "pong"])
def test_other_bare_words_are_plain_messages(word):
    assert _text(word) == {"type": "message", "text": word}


def test_query_string_with_type_is_parsed():
    assert _text("type=message&text=hi&empty=") == {"type": "message", "text": "hi", "empty": ""}


@pytest.mark.parametrize("raw", ["a=1&b=2", "type=message"])
def test_query_string_without_type_or_ampersand_is_plain_message(raw):
    assert _text(raw) == {"type": "message", "text": raw}


def test_plain_text_is_stripped_message():
    assert _text("  오늘 힘들었어  ") == {"type": "message", "text": "오늘 힘들었어"}
    assert _text("") == {"type": "message", "text": ""}


def test_binary_frame_is_rejected():
    with pytest.raises(InvalidPayload, match="binary_frames_not_allowed"):
        _recv({"type": "websocket.receive", "bytes": b"x"})


def test_event_without_text_or_bytes_returns_none():
    assert _recv({"type": "websocket.receive"}) is None


def test_disconnect_event_raises():
    with pytest.raises(WebSocketDisconnect) as exc_info:
        _recv({"type": "websocket.disconnect", "code": 1001})
    assert exc_info.value.code == 1001


def test_disconnect_from_receive_propagates():
    with pytest.raises(WebSocketDisconnect):
        _recv(error=WebSocketDisconnect(1000))


def test_receive_error_returns_none():
    assert _recv(error=RuntimeError("boom")) is None


def test_timeout_returns_ping_by_default():
    assert _recv(hang=True, timeout=0.01) == {"type": "ping"}


def test_timeout_raises_idle_timeout_when_requested():
    with pytest.raises(IdleTimeout):
        _recv(hang=True, timeout=0.01, raise_on_timeout=True)
