# app/services/llm_card.py
from __future__ import annotations

import json
from typing import List

from app.analyze.config import settings
from app.analyze import schemas as sc

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # 테스트 환경 등에서 openai 미설치 대비
    OpenAI = None  # type: ignore


def _get_client():
    if OpenAI is None:
        raise RuntimeError("openai 패키지가 설치되어 있지 않다. requirements.txt를 확인해라.")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않다.")
    return OpenAI(api_key=settings.openai_api_key)


def _format_dialogue(turns: List[sc.ConversationTurn]) -> str:
    """대화 로그를 프롬프트용 텍스트로 변환."""
    lines: List[str] = []
    for t in turns:
        speaker = t.speaker.upper()
        if speaker == "USER":
            name = "사용자"
        elif speaker == "NOA":
            name = "노아"
        else:
            name = speaker
        lines.append(f"{name}: {t.text}")
    return "\n".join(lines)


_SYSTEM_PROMPT = """너는 인지심리학 기반 감정 분석 도구다.
사용자와 상담 AI(노아)의 대화 기록을 보고 다음 필드를 가진 JSON 하나를 생성한다.

반드시 아래 key만 포함한 순수 JSON을 출력하라. 추가 설명을 절대 붙이지 마라.

필드 정의:
- summary: 문자열, 전체 상황을 한 문장으로 요약
- core_emotions: 문자열 배열, 핵심 감정 1~3개 (예: ["불안", "슬픔"])
- situation: 문자열, 사용자가 놓인 상황 설명
- emotion: 문자열, 사용자의 감정 상태를 자연어로 설명
- thoughts: 문자열, 떠오르는 생각/자동사고
- physical_reactions: 문자열, 신체 반응
- behaviors: 문자열, 실제 행동 또는 행동 경향
- coping_actions: 문자열 배열, 사용자가 시도해볼 수 있는 구체적 대처 행동
- tags: 문자열 배열, 주제를 잘 나타내는 키워드 (예: ["시험", "성취압박"])
- insight: 문자열, 사용자가 얻을 수 있는 통찰 한두 문장

출력 형식 예시:
{
  "summary": "...",
  "core_emotions": ["...", "..."],
  "situation": "...",
  "emotion": "...",
  "thoughts": "...",
  "physical_reactions": "...",
  "behaviors": "...",
  "coping_actions": ["...", "..."],
  "tags": ["...", "..."],
  "insight": "..."
}
"""


def analyze_dialogue_to_card(
    turns: List[sc.ConversationTurn],
    title_hint: str | None = None,
) -> sc.CardCreate:
    """
    노아-사용자 대화 로그를 받아서 GPT로 분석카드 내용을 생성하고,
    CardCreate 스키마로 변환해서 반환한다.
    """
    if not turns:
        raise ValueError("conversation_log이 비어 있다.")

    dialogue_text = _format_dialogue(turns)

    # title_hint가 있으면 프롬프트에 살짝 힌트로 넣어줌
    hint_block = f"\n참고 제목 힌트: {title_hint}\n" if title_hint else ""

    user_prompt = (
        "아래는 상담 AI(노아)와 사용자 사이의 대화 로그이다.\n"
        "이 대화 내용을 분석해서 위에서 정의한 JSON 형식으로만 답하라.\n"
        "추가 설명 없이 JSON만 출력하라.\n"
        f"{hint_block}\n"
        "[대화 로그 시작]\n"
        f"{dialogue_text}\n"
        "[대화 로그 끝]\n"
    )

    client = _get_client()

    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("LLM 응답이 비어 있다.")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        # JSON이 아니면 한 번 더 시도한다거나 하는 로직을 나중에 붙여도 됨
        raise RuntimeError(f"LLM 응답 JSON 파싱 실패: {e}") from e

    card = sc.CardCreate(
        summary=data.get("summary"),
        core_emotions=data.get("core_emotions"),
        situation=data.get("situation"),
        emotion=data.get("emotion"),
        thoughts=data.get("thoughts"),
        physical_reactions=data.get("physical_reactions"),
        behaviors=data.get("behaviors"),
        coping_actions=data.get("coping_actions"),
        tags=data.get("tags"),
        insight=data.get("insight"),
    )
    return card
