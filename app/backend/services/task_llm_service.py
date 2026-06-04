from __future__ import annotations

from dataclasses import dataclass

from app.backend.core.prompt_loader import get_task_prompt
from app.core.llm import LLMJsonSchema, LLMMessage
from app.core.llm.providers import get_task_provider

_JSON_POLICY = (
    '출력은 반드시 JSON 배열로만 해. 설명 문장/마크다운/코드블록 없이 [{"title": "...", "description": "..."}, ...] 형식만 반환해.'
)

_TASK_LIST_SCHEMA = LLMJsonSchema(
    name="task_recommendations",
    schema={
        "type": "array",
        "minItems": 1,
        "maxItems": 5,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["title"],
        },
    },
)


@dataclass(frozen=True)
class TaskDraft:
    title: str
    description: str | None = None


@dataclass(frozen=True)
class TaskRecommendationContext:
    emotion_label: str | None = None
    topic: str | None = None
    history_snippet: str = ""



def _clamp_recommendation_count(n: int) -> int:
    return max(1, min(5, int(n)))


def _build_context_block(context: TaskRecommendationContext) -> str:
    parts: list[str] = []
    if context.emotion_label:
        parts.append(f"감정: {context.emotion_label}")
    if context.topic:
        parts.append(f"주제: {context.topic}")
    if context.history_snippet:
        parts.append(f"최근 대화\n{context.history_snippet}")
    return "\n\n".join(parts).strip()


def _normalize_task_drafts(payload: object, *, limit: int | None = None) -> list[TaskDraft]:
    if not isinstance(payload, list):
        raise RuntimeError("GPT 응답 파싱 실패")

    items = payload if limit is None else payload[:limit]
    drafts: list[TaskDraft] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title_raw = item.get("title")
        description_raw = item.get("description")
        title = title_raw.strip() if isinstance(title_raw, str) else ""
        description = description_raw.strip() if isinstance(description_raw, str) else ""
        if not title:
            continue
        drafts.append(TaskDraft(title=title, description=description or None))

    if not drafts:
        raise RuntimeError("유효한 과제가 없습니다")

    return drafts


def recommend_task_drafts_from_prompt(
    *,
    user_prompt: str = "지금 나에게 추천해줘.",
) -> list[TaskDraft]:
    provider = get_task_provider()
    payload = provider.generate_json(
        messages=[
            LLMMessage(role="system", content=f"{get_task_prompt().strip()}\n\n{_JSON_POLICY}"),
            LLMMessage(role="user", content=user_prompt),
        ],
        schema=_TASK_LIST_SCHEMA,
    )
    return _normalize_task_drafts(payload)


def recommend_task_drafts_from_session_context(
    *,
    context: TaskRecommendationContext,
    n: int = 3,
) -> list[TaskDraft]:
    provider = get_task_provider()
    clamped_n = _clamp_recommendation_count(n)
    context_block = _build_context_block(context)
    payload = provider.generate_json(
        messages=[
            LLMMessage(role="system", content=f"{get_task_prompt().strip()}\n\n{_JSON_POLICY}"),
            LLMMessage(role="user", content=f"컨텍스트:\n{context_block}\n\n추천 개수: {clamped_n}"),
        ],
        schema=_TASK_LIST_SCHEMA,
    )
    return _normalize_task_drafts(payload, limit=clamped_n)
