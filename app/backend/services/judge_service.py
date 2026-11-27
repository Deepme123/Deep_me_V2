"""판단기(judge) — 노아 응답 전에 대화 전체를 보고 '진행 메모'를 만든다.

노아는 최근 몇 턴만 보지만 판단기는 대화 전체를 본다. 판단기 프롬프트
(resources/judge_prompt.txt, /prompts/judge로 테스트 서버에서 튜닝)가 JSON만 내면,
여기서 파싱해 노아 프롬프트가 정의한 [진행 메모: ...] 한 줄로 바꿔 사용자 메시지 끝에 붙인다.

판단기는 보조 장치라 어떤 실패(타임아웃, 잘못된 JSON, 프롬프트 없음)에서도 예외를
밖으로 내지 않고 None/빈 메모를 돌려줘 채팅이 항상 정상 동작하게 한다.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from app.core.llm import LLMMessage, LLMRequestOptions
from app.core.llm.providers import get_backend_provider
from app.backend.services.flow_phrases import OFFER, WRAP_GOAL, WRAP_ORDER

logger = logging.getLogger(__name__)

# 판단기는 매 턴 노아 응답 앞에서 동기로 돌기 때문에 짧게 끊는다.
JUDGE_TIMEOUT_SEC = float(os.getenv("JUDGE_TIMEOUT_SEC", "8"))
JUDGE_MAX_TOKENS = int(os.getenv("JUDGE_MAX_TOKENS", "1000"))
# 입력 길이 상한(최근 N개 발화). 대화 전체를 보되 비용 폭주만 막는다.
JUDGE_MAX_MESSAGES = int(os.getenv("JUDGE_MAX_MESSAGES", "80"))

CARD_ITEMS = ("상황", "감정", "신체반응", "생각", "기준", "대처행동", "바람")


@dataclass(frozen=True)
class JudgeResult:
    read: str = ""
    context: str = ""
    thread: str = ""
    deeper: str = ""
    open: bool = False
    insight: str = ""
    offer: bool = False
    want_deep: bool = False
    accept: str = ""
    end_ok: str = ""
    ask_item: str = ""
    ask: str = ""
    covered: tuple[str, ...] = field(default_factory=tuple)
    wrap: bool = False
    risk: bool = False

    @property
    def wants_close(self) -> bool:
        """노아가 마무리를 물었고 사용자가 동의했을 때만 True."""
        return self.end_ok == "예"


def judge_model() -> Optional[str]:
    """JUDGE_MODEL이 있으면 채팅 모델(LLM_MODEL) 대신 쓴다."""
    return (os.getenv("JUDGE_MODEL") or "").strip() or None


def _s(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _b(value: Any) -> bool:
    return value is True


def parse_judge_output(text: str) -> Optional[JudgeResult]:
    """모델 출력에서 JSON 객체를 꺼내 JudgeResult로 정규화한다. 실패 시 None."""
    if not text:
        return None
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    covered = data.get("covered")
    covered_items = tuple(
        c for c in (covered if isinstance(covered, list) else []) if isinstance(c, str) and c in CARD_ITEMS
    )
    return JudgeResult(
        read=_s(data.get("read")),
        context=_s(data.get("context")),
        thread=_s(data.get("thread")),
        deeper=_s(data.get("deeper")),
        open=_b(data.get("open")),
        insight=_s(data.get("insight")),
        offer=_b(data.get("offer")),
        want_deep=_b(data.get("want_deep")),
        accept=_s(data.get("accept")),
        end_ok=_s(data.get("end_ok")),
        ask_item=_s(data.get("ask_item")),
        ask=_s(data.get("ask")),
        covered=covered_items,
        wrap=_b(data.get("wrap")),
        risk=_b(data.get("risk")),
    )


def build_judge_input(
    conversation: list[tuple[str, str]],
    covered: Iterable[str] = frozenset(),
    asked: Iterable[str] = frozenset(),
    remaining: Iterable[str] = (),
) -> str:
    """판단기 입력: [카드 항목] (+[남은 항목]) + [대화](마지막 줄이 사용자가 방금 한 말).

    항목 상태는 판단기 프롬프트 정의대로 나옴 / 물어봤지만 답 없음 / 아직.
    [남은 항목]은 같이 정리하는 중이거나 정리를 제안했을 때만 넣는다.
    """
    covered_set, asked_set = set(covered), set(asked)

    def _status(name: str) -> str:
        if name in covered_set:
            return "나옴"
        if name in asked_set:
            return "물어봤지만 답 없음"
        return "아직"

    items = ", ".join(f"{name}({_status(name)})" for name in CARD_ITEMS)
    head = f"[카드 항목]\n{items}\n\n"
    remaining_list = [r for r in remaining if r]
    if remaining_list:
        head += f"[남은 항목]\n{', '.join(remaining_list)}\n\n"
    recent = conversation[-JUDGE_MAX_MESSAGES:]
    lines = [
        f"{'사용자' if role == 'user' else '노아'}: {text}" for role, text in recent if text
    ]
    return head + "[대화]\n" + "\n".join(lines)


def run_judge(
    judge_prompt: str,
    conversation: list[tuple[str, str]],
    covered: Iterable[str] = frozenset(),
    asked: Iterable[str] = frozenset(),
    remaining: Iterable[str] = (),
) -> Optional[JudgeResult]:
    """판단기를 1회 호출한다(동기, 블로킹 — 호출 측에서 스레드/타임아웃 처리). 실패 시 None."""
    if not judge_prompt or not conversation:
        return None
    try:
        provider = get_backend_provider()
        text = provider.generate_text(
            messages=[
                LLMMessage(role="system", content=judge_prompt),
                LLMMessage(
                    role="user",
                    content=build_judge_input(conversation, covered, asked, remaining),
                ),
            ],
            options=LLMRequestOptions(
                model=judge_model(),
                temperature=0.0,
                max_tokens=JUDGE_MAX_TOKENS,
                timeout_sec=JUDGE_TIMEOUT_SEC,
            ),
        )
    except Exception:
        logger.exception("[Judge] call failed")
        return None
    result = parse_judge_output(text)
    if result is None:
        logger.warning("[Judge] unparsable output | len=%s", len(text or ""))
    return result


def _base_parts(result: JudgeResult) -> list[str]:
    """자유 대화용 기본 메모 조각(읽기 + 짚어 줄 것/더 들어가 볼 것)."""
    parts: list[str] = []
    if result.read:
        parts.append(f"읽기: {result.read}")
    if not result.open:
        if result.insight:
            parts.append(f"짚어 줄 것: {result.insight}")
        else:
            probe = result.deeper or result.thread
            if probe:
                parts.append(f"더 들어가 볼 것: {probe}")
    return parts


def _wrap_memo(parts: list[str]) -> str:
    return f"[진행 메모: {' / '.join(parts)}]" if parts else ""


def build_progress_memo(result: Optional[JudgeResult], *, add_emoji: bool = False) -> str:
    """JudgeResult → 노아 프롬프트의 [진행 메모: ...] 한 줄. 전할 게 없으면 빈 문자열.

    노아 프롬프트가 정의한 메모 종류(읽기/더 들어가 볼 것/짚어 줄 것/이모지/대화 종료)만 쓴다.
    - risk: 메모 없음(노아의 안전 규칙이 메모보다 우선한다).
    - 마무리 동의(end_ok=예): 대화 종료 메모만.
    - open: 캐묻지 않으므로 읽기만 전한다.
    - 짚어 줄 것은 확인 질문("맞아?")을 포함하므로 같은 턴에 더 들어가 볼 것과 같이 내지 않는다.
    """
    if result is None or result.risk:
        return ""
    if result.wants_close:
        return "[진행 메모: 대화 종료]"
    parts = _base_parts(result)
    if add_emoji:
        parts.append("이모지 하나")
    return _wrap_memo(parts)


# ──────────────────────────────────────────────────────────────────────────────
# 데모 1.2 대화 흐름(상태 머신)
#
# 판단기 신호를 모아 대화 단계를 정하고, 단계에 맞는 서버 문구를 진행 메모로 만든다.
#   자유 ──(offer, 4번째 말 이후, 1회)──▶ 제안함 ──(accept≠아니오)──▶ 단계(정리)
#     ▲                                  └─(아니오)─▶ 자유(다시 제안 안 함)
#     └──────────(끝인사 직전 end_ok=아니오)──── 마무리(핵심→바람→해주고픈말→마무리→끝인사)
#   단계 → 마무리: 필수 5개가 다 나왔거나 물어봤을 때, 정리 9턴 경과, 또는 판단기 wrap.
# 상태는 JSON으로 세션에 저장한다(EmotionSession.flow_state).

FLOW_FREE = "자유"
FLOW_OFFERED = "제안함"
FLOW_DEEP = "단계"
FLOW_DONE = "종료"
_FLOWS = (FLOW_FREE, FLOW_OFFERED, FLOW_DEEP, FLOW_DONE)

REQUIRED_ITEMS: tuple[str, ...] = ("상황", "감정", "생각", "기준", "대처행동")
FLOW_OFFER_MIN_USER_COUNT = int(os.getenv("FLOW_OFFER_MIN_USER_COUNT", "4"))
FLOW_DEEP_MAX_TURNS = int(os.getenv("FLOW_DEEP_MAX_TURNS", "9"))


def default_flow_state() -> dict[str, Any]:
    return {
        "flow": FLOW_FREE,
        "covered": [],
        "asked": [],
        "offers": 0,
        "declined": False,
        "deep_at": -1,
        "wrap": None,
        "wrap_idx": 0,
    }


def normalize_flow_state(raw: Any) -> dict[str, Any]:
    """DB에서 읽은 값을 검증해 완전한 상태로 만든다. 깨진 값은 기본값으로."""
    state = default_flow_state()
    if not isinstance(raw, dict):
        return state
    if raw.get("flow") in _FLOWS:
        state["flow"] = raw["flow"]
    for key in ("covered", "asked"):
        val = raw.get(key)
        if isinstance(val, list):
            state[key] = [c for c in CARD_ITEMS if c in val]
    for key in ("offers", "deep_at", "wrap_idx"):
        val = raw.get(key)
        if isinstance(val, int) and not isinstance(val, bool):
            state[key] = val
    state["declined"] = raw.get("declined") is True
    wrap = raw.get("wrap")
    if isinstance(wrap, list) and wrap and all(w in WRAP_GOAL for w in wrap):
        state["wrap"] = list(wrap)
        state["wrap_idx"] = max(0, min(state["wrap_idx"], len(wrap) - 1))
    else:
        state["wrap"] = None
        state["wrap_idx"] = 0
    return state


def in_guided_flow(state: dict[str, Any]) -> bool:
    """정리를 제안했거나 정리/마무리 중이면 True(액티비티 제안 등 다른 개입을 막는 데 쓴다)."""
    return state.get("flow") in (FLOW_OFFERED, FLOW_DEEP)


def remaining_items(state: dict[str, Any]) -> list[str]:
    """판단기에 넘길 [남은 항목]. 제안함/정리 중(마무리 전)일 때만."""
    if state.get("flow") not in (FLOW_OFFERED, FLOW_DEEP) or state.get("wrap"):
        return []
    done = set(state.get("covered") or []) | set(state.get("asked") or [])
    return [i for i in REQUIRED_ITEMS if i not in done]


def count_user_messages(conversation: list[tuple[str, str]]) -> int:
    return sum(1 for role, text in conversation if role == "user" and text)


@dataclass(frozen=True)
class FlowDecision:
    memo: str
    state: dict[str, Any]
    # 마무리 지시가 있는 턴: 이른 턴의 [[CONFIRM_CLOSE]]도 의도된 종료로 본다.
    close_ordered: bool = False
    # 끝인사 턴: 노아가 토큰을 빠뜨려도 답을 보낸 뒤 서버가 대화를 종료한다.
    force_close: bool = False
    stage: str = ""  # 로그용(자유/제안/정리/마무리:핵심 …)


def _merge_items(existing: list[str], new: Iterable[str]) -> list[str]:
    merged = set(existing) | set(new)
    return [c for c in CARD_ITEMS if c in merged]


def build_flow_memo(
    state: Any,
    result: Optional[JudgeResult],
    user_count: int,
    *,
    add_emoji: bool = False,
) -> FlowDecision:
    """상태 + 판단 결과 → (진행 메모, 새 상태). 순수 함수(DB·LLM 없음).

    - 판단 실패(None) 또는 risk: 메모 없이 상태를 그대로 둔다(안전 규칙 우선).
    - user_count: 이번 말을 포함한 사용자 발화 수.
    """
    st = normalize_flow_state(copy.deepcopy(state))
    if result is None or result.risk:
        return FlowDecision("", st, stage="보류")

    st["covered"] = _merge_items(st["covered"], result.covered)

    # 직전에 정리를 제안했으면 이번 답으로 수락 여부를 정한다.
    if st["flow"] == FLOW_OFFERED:
        if result.accept == "아니오":
            st["flow"] = FLOW_FREE
            st["declined"] = True
        else:
            st["flow"] = FLOW_DEEP
            st["deep_at"] = user_count
    elif st["flow"] == FLOW_FREE and result.want_deep and not st["declined"]:
        st["flow"] = FLOW_DEEP
        st["deep_at"] = user_count

    # 정리 중 → 마무리 시작 조건
    if st["flow"] == FLOW_DEEP and not st["wrap"]:
        all_touched = not remaining_items(st)
        timed_out = st["deep_at"] >= 0 and user_count - st["deep_at"] >= FLOW_DEEP_MAX_TURNS
        if all_touched or timed_out or result.wrap:
            st["wrap"] = list(WRAP_ORDER)
            st["wrap_idx"] = 0

    # 마무리 중: 한 칸씩 진행
    if st["wrap"]:
        step = st["wrap"][st["wrap_idx"]]
        if step == "끝인사" and result.end_ok == "아니오":
            # 마무리할지 물었는데 더 얘기하고 싶다고 했다 → 자유 대화로 돌아간다(재제안 없음).
            st["flow"], st["wrap"], st["wrap_idx"] = FLOW_FREE, None, 0
            st["declined"] = True
            parts = _base_parts(result)
            if add_emoji:
                parts.append("이모지 하나")
            return FlowDecision(_wrap_memo(parts), st, stage="자유(마무리 취소)")
        parts = [f"이번에 할 것: {WRAP_GOAL[step]}"]
        if step == "끝인사":
            parts.append("대화 종료")
            st["flow"] = FLOW_DONE
            st["wrap"], st["wrap_idx"] = None, 0
            return FlowDecision(
                _wrap_memo(parts), st, close_ordered=True, force_close=True, stage="마무리:끝인사"
            )
        st["wrap_idx"] += 1
        return FlowDecision(_wrap_memo(parts), st, stage=f"마무리:{step}")

    # 마무리 밖에서 노아가 마무리를 물었고 사용자가 동의 → 기존 동작대로 종료 메모.
    if result.wants_close:
        return FlowDecision("[진행 메모: 대화 종료]", st, close_ordered=True, stage="종료 동의")

    if st["flow"] == FLOW_DEEP:
        parts = []
        if result.read:
            parts.append(f"읽기: {result.read}")
        remaining = remaining_items(st)
        if result.open:
            pass  # 캐묻지 않는다
        elif result.insight:
            parts.append(f"짚어 줄 것: {result.insight}")
        elif result.ask and result.ask_item in remaining:
            parts.append(f"물어볼 것: {result.ask}")
            st["asked"] = _merge_items(st["asked"], [result.ask_item])
        elif result.deeper or result.thread:
            parts.append(f"더 들어가 볼 것: {result.deeper or result.thread}")
        return FlowDecision(_wrap_memo(parts), st, stage="정리")

    if (
        st["flow"] == FLOW_FREE
        and result.offer
        and user_count >= FLOW_OFFER_MIN_USER_COUNT
        and st["offers"] == 0
        and not st["declined"]
    ):
        st["flow"] = FLOW_OFFERED
        st["offers"] += 1
        parts = []
        if result.read:
            parts.append(f"읽기: {result.read}")
        parts.append(f"이번에 할 것: {OFFER}")
        return FlowDecision(_wrap_memo(parts), st, stage="제안")

    parts = _base_parts(result)
    if add_emoji:
        parts.append("이모지 하나")
    return FlowDecision(_wrap_memo(parts), st, stage=st["flow"])


def attach_memo(conversation: list[tuple[str, str]], memo: str) -> list[tuple[str, str]]:
    """마지막 사용자 메시지 끝에 메모를 붙인 새 대화 목록을 돌려준다(DB에는 저장하지 않는다)."""
    if not memo or not conversation or conversation[-1][0] != "user":
        return conversation
    role, text = conversation[-1]
    return [*conversation[:-1], (role, f"{text}\n\n{memo}")]
