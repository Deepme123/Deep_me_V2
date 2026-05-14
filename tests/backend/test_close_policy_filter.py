from __future__ import annotations

import pytest

from app.backend.services.close_policy import (
    RESERVED_CONFIRM_CLOSE_TOKEN,
    StreamingConfirmCloseFilter,
)


def _feed_all(filter_obj: StreamingConfirmCloseFilter, pieces: list[str]) -> str:
    out = ""
    for piece in pieces:
        out += filter_obj.feed(piece)
    out += filter_obj.flush()
    return out


def test_filter_passes_through_text_without_token():
    f = StreamingConfirmCloseFilter()
    out = _feed_all(f, ["hello ", "world", " bye"])
    assert out == "hello world bye"
    assert f.end_detected is False


def test_filter_detects_token_at_end_of_single_piece():
    f = StreamingConfirmCloseFilter()
    out = _feed_all(f, [f"마무리 멘트.{RESERVED_CONFIRM_CLOSE_TOKEN}"])
    assert RESERVED_CONFIRM_CLOSE_TOKEN not in out
    assert out == "마무리 멘트."
    assert f.end_detected is True


def test_filter_detects_token_split_across_chunks():
    f = StreamingConfirmCloseFilter()
    out = _feed_all(f, ["오늘은 여기까지. ", "[[CONF", "IRM_CLO", "SE]]"])
    assert RESERVED_CONFIRM_CLOSE_TOKEN not in out
    # whitespace immediately before the token is stripped (legacy behavior)
    assert out == "오늘은 여기까지."
    assert f.end_detected is True


def test_filter_detects_token_split_one_char_per_chunk():
    f = StreamingConfirmCloseFilter()
    pieces = ["prefix "] + list(RESERVED_CONFIRM_CLOSE_TOKEN)
    out = _feed_all(f, pieces)
    assert RESERVED_CONFIRM_CLOSE_TOKEN not in out
    assert out == "prefix"
    assert f.end_detected is True


def test_filter_does_not_leak_partial_token_during_feed():
    f = StreamingConfirmCloseFilter()
    safe1 = f.feed("hello ")
    # Trailing whitespace is held back so it can be stripped together with
    # the token if it ends up immediately preceding one.
    assert "[" not in safe1
    safe2 = f.feed("[[")
    assert safe2 == ""
    safe3 = f.feed("CONFIRM")
    assert safe3 == ""
    safe4 = f.feed("_CLOSE]]")
    assert safe4 == ""
    tail = f.flush()
    assert tail == ""
    assert f.end_detected is True
    # Across the whole stream the visible text should be "hello" (token and
    # its leading whitespace were absorbed).
    assert safe1.rstrip() == "hello"


def test_filter_releases_holdback_when_prefix_match_breaks():
    f = StreamingConfirmCloseFilter()
    safe1 = f.feed("ok [")
    safe2 = f.feed("not-token text")
    tail = f.flush()
    full = safe1 + safe2 + tail
    assert full == "ok [not-token text"
    assert f.end_detected is False


def test_filter_drops_text_after_detected_token():
    f = StreamingConfirmCloseFilter()
    out = _feed_all(
        f,
        [f"마무리. {RESERVED_CONFIRM_CLOSE_TOKEN} 이건 무시", " 더 무시"],
    )
    assert RESERVED_CONFIRM_CLOSE_TOKEN not in out
    assert "무시" not in out
    assert out == "마무리."
    assert f.end_detected is True


def test_filter_handles_empty_pieces():
    f = StreamingConfirmCloseFilter()
    assert f.feed("") == ""
    assert f.feed("hi") == "hi"
    assert f.flush() == ""
    assert f.end_detected is False


def test_filter_flush_emits_remaining_pending():
    f = StreamingConfirmCloseFilter()
    # Feed a 1-char prefix that matches start of token, then flush without completing
    safe = f.feed("hello [")
    tail = f.flush()
    assert safe + tail == "hello ["
    assert f.end_detected is False


@pytest.mark.parametrize("split_at", range(1, len(RESERVED_CONFIRM_CLOSE_TOKEN)))
def test_filter_split_at_every_position(split_at: int):
    f = StreamingConfirmCloseFilter()
    full = f"끝 멘트. {RESERVED_CONFIRM_CLOSE_TOKEN}"
    boundary = len(full) - len(RESERVED_CONFIRM_CLOSE_TOKEN) + split_at
    out = _feed_all(f, [full[:boundary], full[boundary:]])
    assert RESERVED_CONFIRM_CLOSE_TOKEN not in out
    assert out == "끝 멘트."
    assert f.end_detected is True
