from __future__ import annotations

from typing import List
from uuid import UUID

from sqlmodel import Session, select

from app.backend.db.session import session_scope
from app.backend.models.emotion import EmotionSession, EmotionStep
from app.backend.models.task import Task
from app.backend.services.task_llm_service import (
    TaskDraft,
    TaskRecommendationContext,
    recommend_task_drafts_from_session_context,
)


def _condense_history(lines: list[str], max_chars: int) -> str:
    combined = "\n".join(lines).strip()
    return combined if len(combined) <= max_chars else ("...\n" + combined[-max_chars:])


def load_task_recommendation_context(
    db: Session,
    *,
    user_id: UUID,
    session_id: UUID,
    recent_steps_limit: int = 10,
    max_history_chars: int = 1000,
) -> TaskRecommendationContext:
    sess = db.get(EmotionSession, session_id)
    if not sess or sess.user_id != user_id:
        raise ValueError("Emotion session not found or not owned by user")

    stmt = (
        select(EmotionStep)
        .where(EmotionStep.session_id == session_id)
        .order_by(EmotionStep.created_at.desc())
        .limit(recent_steps_limit)
    )
    steps = list(reversed(db.exec(stmt).all()))

    history_lines = [
        f"유저: {step.user_input or ''}\nGPT: {step.gpt_response or ''}".strip()
        for step in steps
        if (step.user_input or step.gpt_response)
    ]

    return TaskRecommendationContext(
        emotion_label=sess.emotion_label,
        topic=sess.topic,
        history_snippet=_condense_history(history_lines, max_history_chars),
    )


def persist_task_drafts(
    db: Session,
    *,
    user_id: UUID,
    drafts: list[TaskDraft],
) -> list[Task]:
    if not drafts:
        raise RuntimeError("유효한 과제가 없습니다")

    tasks = [
        Task(
            user_id=user_id,
            title=draft.title,
            description=draft.description,
        )
        for draft in drafts
    ]

    try:
        for task in tasks:
            db.add(task)
        db.commit()
    except Exception:
        db.rollback()
        raise

    for task in tasks:
        db.refresh(task)

    return tasks


def recommend_tasks_from_session_core(
    *,
    user_id: UUID,
    session_id: UUID,
    n: int = 3,
    recent_steps_limit: int = 10,
    max_history_chars: int = 1000,
) -> List[Task]:
    with session_scope() as db:
        context = load_task_recommendation_context(
            db,
            user_id=user_id,
            session_id=session_id,
            recent_steps_limit=recent_steps_limit,
            max_history_chars=max_history_chars,
        )
        drafts = recommend_task_drafts_from_session_context(context=context, n=n)
        return persist_task_drafts(db, user_id=user_id, drafts=drafts)
