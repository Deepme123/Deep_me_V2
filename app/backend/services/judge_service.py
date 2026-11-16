"""판단기(judge) — 노아 응답 전에 대화 전체를 보고 '진행 메모'를 만든다.

노아는 최근 몇 턴만 보지만 판단기는 대화 전체를 본다. 판단기 프롬프트
(resources/judge_prompt.txt, /prompts/judge로 테스트 서버에서 튜닝)가 JSON만 내면,
여기서 파싱해 노아 프롬프트가 정의한 [진행 메모: ...] 한 줄로 바꿔 사용자 메시지 끝에 붙인다.

판단기는 보조 장치라 어떤 실패(타임아웃, 잘못된 JSON, 프롬프트 없음)에서도 예외를
밖으로 내지 않고 None/빈 메모를 돌려줘 채팅이 항상 정상 동작하게 한다.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.llm import LLMMessage, LLMRequestOptions
from app.core.llm.providers import get_backend_provider

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
    covered: frozenset[str] | set[str] = frozenset(),
) -> str:
    """판단기 입력: [카드 항목] + [대화](마지막 줄이 사용자가 방금 한 말)."""
    items = ", ".join(
        f"{name}({'나옴' if name in covered else '아직'})" for name in CARD_ITEMS
    )
    recent = conversation[-JUDGE_MAX_MESSAGES:]
    lines = [
        f"{'사용자' if role == 'user' else '노아'}: {text}" for role, text in recent if text
    ]
    return f"[카드 항목]\n{items}\n\n[대화]\n" + "\n".join(lines)


def run_judge(
    judge_prompt: str,
    conversation: list[tuple[str, str]],
    covered: frozenset[str] | set[str] = frozenset(),
) -> Optional[JudgeResult]:
    """판단기를 1회 호출한다(동기, 블로킹 — 호출 측에서 스레드/타임아웃 처리). 실패 시 None."""
    if not judge_prompt or not conversation:
        return None
    try:
        provider = get_backend_provider()
        text = provider.generate_text(
            messages=[
                LLMMessage(role="system", content=judge_prompt),
                LLMMessage(role="user", content=build_judge_input(conversation, covered)),
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
    if add_emoji:
        parts.append("이모지 하나")
    return f"[진행 메모: {' / '.join(parts)}]" if parts else ""


def attach_memo(conversation: list[tuple[str, str]], memo: str) -> list[tuple[str, str]]:
    """마지막 사용자 메시지 끝에 메모를 붙인 새 대화 목록을 돌려준다(DB에는 저장하지 않는다)."""
    if not memo or not conversation or conversation[-1][0] != "user":
        return conversation
    role, text = conversation[-1]
    return [*conversation[:-1], (role, f"{text}\n\n{memo}")]
