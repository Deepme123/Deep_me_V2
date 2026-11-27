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


# ---- 데모 1.2 흐름(상태 머신) ----

from app.backend.services.flow_phrases import OFFER, WRAP_GOAL, WRAP_ORDER  # noqa: E402
from app.backend.services.judge_service import (  # noqa: E402
    build_flow_memo,
    default_flow_state,
    normalize_flow_state,
    remaining_items,
)


def test_build_judge_input_marks_asked_and_remaining():
    text = build_judge_input(
        [("user", "속상해")], covered={"상황"}, asked={"감정"}, remaining=["감정", "생각"]
    )
    assert "감정(물어봤지만 답 없음)" in text
    assert "[남은 항목]\n감정, 생각" in text
    assert "[남은 항목]" not in build_judge_input([("user", "x")])


def test_offer_only_from_fourth_user_message_and_only_once():
    st = default_flow_state()
    d = build_flow_memo(st, JudgeResult(offer=True, thread="t"), 3)
    assert OFFER not in d.memo and d.state["flow"] == "자유"
    d = build_flow_memo(st, JudgeResult(offer=True), 4)
    assert f"이번에 할 것: {OFFER}" in d.memo and d.state["flow"] == "제안함"
    assert d.state["offers"] == 1


def test_declined_offer_returns_to_free_and_never_reoffers():
    st = {**default_flow_state(), "flow": "제안함", "offers": 1}
    d = build_flow_memo(st, JudgeResult(accept="아니오", thread="t"), 5)
    assert d.state["flow"] == "자유" and d.state["declined"] is True
    d = build_flow_memo(d.state, JudgeResult(offer=True), 6)
    assert OFFER not in d.memo


def test_accept_enters_deep_and_asks_remaining_item():
    st = {**default_flow_state(), "flow": "제안함", "offers": 1}
    d = build_flow_memo(
        st, JudgeResult(accept="예", covered=("상황",), ask_item="감정", ask="그때 어땠어"), 5
    )
    assert d.state["flow"] == "단계" and d.state["deep_at"] == 5
    assert d.memo == "[진행 메모: 물어볼 것: 그때 어땠어]"
    assert d.state["asked"] == ["감정"]
    assert remaining_items(d.state) == ["생각", "기준", "대처행동"]


def test_ask_for_item_not_remaining_is_ignored():
    st = {**default_flow_state(), "flow": "단계", "deep_at": 5, "covered": ["상황"]}
    d = build_flow_memo(st, JudgeResult(ask_item="상황", ask="q", thread="t"), 6)
    assert "물어볼 것" not in d.memo and "더 들어가 볼 것: t" in d.memo


def _run_wrap(state, start_count):
    stages, d = [], None
    for i, _ in enumerate(WRAP_ORDER):
        d = build_flow_memo(state, JudgeResult(), start_count + i)
        stages.append(d.stage)
        state = d.state
    return stages, d


def test_all_required_items_touched_starts_wrap_in_order_and_closes():
    st = {
        **default_flow_state(),
        "flow": "단계",
        "deep_at": 5,
        "covered": ["상황", "감정", "생각"],
        "asked": ["기준"],
    }
    first = build_flow_memo(st, JudgeResult(covered=("대처행동",)), 8)
    assert first.memo == f"[진행 메모: 이번에 할 것: {WRAP_GOAL['핵심']}]"
    stages, last = _run_wrap(st | {"covered": st["covered"] + ["대처행동"]}, 8)
    assert stages == [f"마무리:{w}" for w in WRAP_ORDER]
    assert last.memo.endswith("/ 대화 종료]")
    assert last.force_close and last.close_ordered
    assert last.state["flow"] == "종료"


def test_deep_times_out_after_nine_turns():
    st = {**default_flow_state(), "flow": "단계", "deep_at": 5}
    assert build_flow_memo(st, JudgeResult(), 13).stage == "정리"
    assert build_flow_memo(st, JudgeResult(), 14).stage == "마무리:핵심"


def test_declining_wrap_before_goodbye_returns_to_free():
    st = {**default_flow_state(), "flow": "단계", "wrap": list(WRAP_ORDER), "wrap_idx": 4}
    d = build_flow_memo(st, JudgeResult(end_ok="아니오", thread="t"), 15)
    assert not d.force_close and d.state["flow"] == "자유" and d.state["wrap"] is None
    assert "대화 종료" not in d.memo


def test_risk_or_judge_failure_keeps_state_and_no_memo():
    st = {**default_flow_state(), "flow": "단계", "deep_at": 5}
    for r in (None, JudgeResult(risk=True, ask_item="감정", ask="q", covered=("감정",))):
        d = build_flow_memo(st, r, 6)
        assert d.memo == "" and d.state == normalize_flow_state(st)


def test_normalize_flow_state_repairs_garbage():
    assert normalize_flow_state(None) == default_flow_state()
    st = normalize_flow_state({"flow": "??", "covered": ["감정", "x"], "wrap": ["없음"], "offers": True})
    assert st["flow"] == "자유" and st["covered"] == ["감정"] and st["wrap"] is None and st["offers"] == 0
