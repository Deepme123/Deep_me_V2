from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Callable, TypeVar
from uuid import UUID

from sqlmodel import Session, select

from app.backend.db.session import session_scope
from app.backend.models.emotion import EmotionSession, EmotionStep
from app.backend.schemas.emotion import EmotionCloseRequest
from app.backend.services.convo_policy import ACTIVITY_STEP_TYPE, is_activity_turn
from app.backend.services.ws_utils import transcript_rows_to_conversation

T = TypeVar("T")


def run_with_session(fn: Callable[[Session], T], *args, **kwargs) -> T:
    with session_scope() as db:
        return fn(db, *args, **kwargs)


async def with_db(fn: Callable[[Session], T], *args, **kwargs) -> T:
    return await asyncio.to_thread(run_with_session, fn, *args, **kwargs)


def create_emotion_session(db: Session, user_id: UUID | None) -> EmotionSession:
    session = EmotionSession(
        user_id=user_id,
        started_at=datetime.utcnow(),
        emotion_label=None,
        topic=None,
        trigger_summary=None,
        insight_summary=None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def prepare_message_context(
    db: Session,
    session_id: UUID,
    user_text: str,
    *,
    ws_history_turns: int,
    already_fired: bool | None = None,
) -> dict:
    max_entries = ws_history_turns * 2
    # (session_id, step_order) 복합 인덱스를 역순으로 타서 LIMIT 적용 후 뒤집음.
    # ORDER BY created_at은 인덱스가 없어 풀스캔+정렬이 발생하므로 step_order 사용.
    rows: list[EmotionStep] = list(
        db.exec(
            select(EmotionStep)
            .where(EmotionStep.session_id == session_id)
            .order_by(EmotionStep.step_order.desc())
            .limit(max_entries)
        )
    )
    rows.reverse()

    last_order = rows[-1].step_order if rows else 0

    want_activity = is_activity_turn(
        user_text=user_text,
        db=db,
        session_id=session_id,
        steps=rows,
        already_fired=already_fired,
    )

    user_order = last_order + 1
    assistant_order = user_order + 1
    conversation = transcript_rows_to_conversation(rows) + [("user", user_text)]
    return {
        "transcript_rows": rows,
        "want_activity": want_activity,
        "user_order": user_order,
        "assistant_order": assistant_order,
        "conversation": conversation,
    }


def commit_full_turn(
    db: Session,
    session_id: UUID,
    user_text: str,
    assistant_text: str,
    user_order: int,
    assistant_order: int,
    *,
    add_activity_marker: bool,
) -> None:
    user_step = EmotionStep(
        session_id=session_id,
        step_order=user_order,
        step_type="user",
        user_input=user_text,
        gpt_response="",
        created_at=datetime.utcnow(),
        insight_tag=None,
    )
    assistant_step = EmotionStep(
        session_id=session_id,
        step_order=assistant_order,
        step_type="assistant",
        user_input="",
        gpt_response=assistant_text,
        created_at=datetime.utcnow(),
        insight_tag=None,
    )
    db.add(user_step)
    db.add(assistant_step)

    if add_activity_marker:
        marker = EmotionStep(
            session_id=session_id,
            step_order=assistant_order + 1,
            step_type=ACTIVITY_STEP_TYPE,
            user_input="",
            gpt_response="",
            created_at=datetime.utcnow(),
            insight_tag=None,
        )
        db.add(marker)

    db.commit()


def close_session_record(db: Session, session_id: UUID, payload: EmotionCloseRequest) -> None:
    session = db.get(EmotionSession, session_id)
    if session:
        session.ended_at = datetime.utcnow()
        if payload.emotion_label:
            session.emotion_label = payload.emotion_label
        if payload.topic:
            session.topic = payload.topic
        if payload.trigger_summary:
            session.trigger_summary = payload.trigger_summary
        if payload.insight_summary:
            session.insight_summary = payload.insight_summary
        db.add(session)
        db.commit()


def append_step_marker(db: Session, session_id: UUID, step_type: str) -> None:
    last_order = db.exec(
        select(EmotionStep.step_order)
        .where(EmotionStep.session_id == session_id)
        .order_by(EmotionStep.step_order.desc())
        .limit(1)
    ).first()
    marker = EmotionStep(
        session_id=session_id,
        step_order=int(last_order or 0) + 1,
        step_type=step_type,
        user_input="",
        gpt_response="",
        created_at=datetime.utcnow(),
        insight_tag=None,
    )
    db.add(marker)
    db.commit()
