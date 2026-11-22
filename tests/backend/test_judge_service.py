from __future__ import annotations

from app.backend.services import judge_service as js
from app.backend.services.judge_service import (
    JudgeResult,
    attach_memo,
    build_judge_input,
    build_progress_memo,
    parse_judge_output,
)


def test_parse_extracts_json_from_noisy_text_and_normalizes():
    raw = '결과: {"read":"반어","open":false,"covered":["상황","없는항목",3],"risk":true,"end_ok":" 예 "} 끝'
    r = parse_judge_output(raw)
    assert r.read == "반어"
    assert r.covered == ("상황",)
    assert r.risk is True
    assert r.wants_close is True


def test_parse_rejects_garbage():
    assert parse_judge_output("") is None
    assert parse_judge_output("no json") is None
    assert parse_judge_output("{broken") is None
    assert parse_judge_output("[1,2]") is None


def test_parse_treats_non_bool_flags_as_false():
    r = parse_judge_output('{"risk":"true","wrap":1}')
    assert r.risk is False and r.wrap is False


def test_build_judge_input_marks_covered_and_keeps_last_user_line_last():
    text = build_judge_input([("user", "안녕"), ("assistant", "왔네"), ("user", "속상해")], {"상황"})
    assert "상황(나옴)" in text and "감정(아직)" in text
    assert text.rstrip().endswith("사용자: 속상해")


def test_memo_empty_when_nothing_or_risk():
    assert build_progress_memo(None) == ""
    assert build_progress_memo(JudgeResult()) == ""
    assert build_progress_memo(JudgeResult(read="x", thread="y", risk=True)) == ""


def test_memo_close_only_when_user_agreed():
    r = JudgeResult(end_ok="예", read="x", thread="y")
    assert build_progress_memo(r) == "[진행 메모: 대화 종료]"
    assert build_progress_memo(JudgeResult(wrap=True, end_ok="")) == ""


def test_memo_insight_replaces_probe_and_open_suppresses_probe():
    r = JudgeResult(read="r", insight="연결", deeper="d", thread="t")
    assert build_progress_memo(r) == "[진행 메모: 읽기: r / 짚어 줄 것: 연결]"
    r = JudgeResult(deeper="d", thread="t")
    assert build_progress_memo(r) == "[진행 메모: 더 들어가 볼 것: d]"
    assert build_progress_memo(JudgeResult(thread="t")) == "[진행 메모: 더 들어가 볼 것: t]"
    r = JudgeResult(read="r", thread="t", insight="i", open=True)
    assert build_progress_memo(r) == "[진행 메모: 읽기: r]"


def test_memo_emoji_only_part():
    assert build_progress_memo(JudgeResult(), add_emoji=True) == "[진행 메모: 이모지 하나]"


def test_attach_memo_appends_to_last_user_without_mutating_input():
    conv = [("user", "a"), ("assistant", "b"), ("user", "c")]
    out = attach_memo(conv, "[진행 메모: x]")
    assert out[-1] == ("user", "c\n\n[진행 메모: x]")
    assert conv[-1] == ("user", "c")
    assert attach_memo(conv, "") is conv
    assert attach_memo([("assistant", "z")], "m") == [("assistant", "z")]


def test_run_judge_returns_none_on_failure_or_empty_prompt(monkeypatch):
    assert js.run_judge("", [("user", "a")]) is None
    assert js.run_judge("p", []) is None

    class Boom:
        def generate_text(self, **_):
            raise RuntimeError("down")

    monkeypatch.setattr(js, "get_backend_provider", lambda: Boom())
    assert js.run_judge("p", [("user", "a")]) is None


def test_run_judge_parses_provider_output(monkeypatch):
    seen = {}

    class Ok:
        def generate_text(self, *, messages, options):
            seen["options"] = options
            seen["system"] = messages[0].content
            return '{"thread":"언제부터인지"}'

    monkeypatch.setattr(js, "get_backend_provider", lambda: Ok())
    monkeypatch.setenv("JUDGE_MODEL", "small-model")
    r = js.run_judge("judge-prompt", [("user", "a")])
    assert r.thread == "언제부터인지"
    assert seen["system"] == "judge-prompt"
    assert seen["options"].model == "small-model"
    assert seen["options"].temperature == 0.0
