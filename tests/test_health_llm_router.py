from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.routers import health_llm


def test_health_llm_calls_generate_with_current_signature(monkeypatch):
    captured: dict = {}

    def fake_generate_noa_response(
        *,
        system_prompt,
        task_prompt,
        conversation,
        temperature=None,
        max_tokens=800,
        model=None,
    ):
        captured["system_prompt"] = system_prompt
        captured["task_prompt"] = task_prompt
        captured["conversation"] = conversation
        return "pong"

    monkeypatch.setattr(health_llm, "generate_noa_response", fake_generate_noa_response)

    result = health_llm.health_llm(q=None)

    assert result["ok"] is True
    assert "pong" in result["text"].lower()
    assert captured["system_prompt"] == "(healthcheck)"
    assert captured["task_prompt"] is None
    assert captured["conversation"][-1][0] == "user"


def test_health_llm_stream_ok_and_contract(monkeypatch):
    captured: dict = {}

    def fake_stream_noa_response(
        *,
        system_prompt,
        task_prompt,
        conversation,
        temperature=None,
        max_tokens=800,
        model=None,
    ):
        captured["system_prompt"] = system_prompt
        captured["task_prompt"] = task_prompt
        captured["conversation"] = conversation
        yield "po"
        yield "ng"

    monkeypatch.setattr(health_llm, "stream_noa_response", fake_stream_noa_response)

    result = health_llm.health_llm_stream(q=None)

    assert result["ok"] is True
    assert result["tokens"] == 2
    assert result["text"] == "pong"
    assert captured["system_prompt"] == "(healthcheck-stream)"
    assert captured["task_prompt"] is None
    assert captured["conversation"][-1][0] == "user"


def test_health_llm_stream_maps_blocked_by_content_filter(monkeypatch):
    def fake_stream_noa_response(**kwargs):
        raise RuntimeError("blocked_by_content_filter")
        yield ""  # pragma: no cover

    monkeypatch.setattr(health_llm, "stream_noa_response", fake_stream_noa_response)

    with pytest.raises(HTTPException) as excinfo:
        health_llm.health_llm_stream(q=None)

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail == "blocked_by_content_filter"


def test_health_llm_stream_empty_response(monkeypatch):
    def fake_stream_noa_response(**kwargs):
        yield "   "

    monkeypatch.setattr(health_llm, "stream_noa_response", fake_stream_noa_response)

    with pytest.raises(HTTPException) as excinfo:
        health_llm.health_llm_stream(q=None)

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail == "llm_stream_empty"
