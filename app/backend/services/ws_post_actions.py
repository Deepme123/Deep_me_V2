from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder

from app.backend.db.session import session_scope
from app.backend.models.emotion import EmotionSession
from app.backend.schemas.emotion import EmotionCloseRequest, EmotionCloseResponse
from app.backend.services.task_recommend import recommend_tasks_from_session_core
from app.backend.services.ws_utils import safe_str


async def recommend_tasks_async(session_id: UUID, max_items: int) -> list[dict]:
    def _work() -> list[dict]:
        with session_scope() as db:
            session = db.get(EmotionSession, session_id)
            if not session or not session.user_id:
                return []
            user_id = session.user_id

        tasks = recommend_tasks_from_session_core(
            user_id=user_id,
            session_id=session_id,
            n=max(1, max_items),
        )
        return jsonable_encoder(tasks, exclude_none=True) if tasks else []

    return await asyncio.to_thread(_work)


async def generate_analysis_card_async(session_id: UUID) -> dict:
    def _work() -> dict:
        from app.analyze.routers.cards import (
            _load_session_conversation_turns,
            _analyze_and_store_card,
        )

        with session_scope() as db:
            turns = _load_session_conversation_turns(db, session_id)
            card = _analyze_and_store_card(
                db=db,
                session_id=session_id,
                turns=turns,
            )
        return jsonable_encoder(card, exclude_none=True)

    return await asyncio.to_thread(_work)


async def finalize_close(
    *,
    session_id: UUID | None,
    payload: EmotionCloseRequest,
    trigger_analysis_card: bool,
    close_session_record: Callable[[UUID, EmotionCloseRequest], Awaitable[None]],
    flush_outbound_messages: Callable[[], Awaitable[None]],
    send_immediate: Callable[[dict], Awaitable[None]],
    generate_analysis_card: Callable[[UUID], Awaitable[dict]],
    analysis_card_timeout: float,
    logger: logging.Logger,
) -> bool:
    try:
        if session_id is None:
            raise ValueError("session_id is required")
        await close_session_record(session_id, payload)
    except Exception as exc:
        logger.warning("WS close update failed | %s", safe_str(exc))
        await send_immediate({"type": "error", "message": "close_failed"})
        return False

    await flush_outbound_messages()
    await send_immediate(EmotionCloseResponse(type="close_ok").model_dump())

    if trigger_analysis_card and session_id is not None:
        try:
            card = await asyncio.wait_for(
                generate_analysis_card(session_id),
                timeout=analysis_card_timeout,
            )
        except Exception as exc:
            logger.exception(
                "analysis card generation failed after close | session_id=%s | %s",
                session_id,
                safe_str(exc),
            )
            await send_immediate(
                {
                    "type": "analysis_card_failed",
                    "session_id": session_id,
                    "message": "analysis_card_generation_failed",
                }
            )
        else:
            await send_immediate(
                {
                    "type": "analysis_card_ready",
                    "session_id": session_id,
                    "card": card,
                }
            )
    return True


async def enter_close_cooldown(
    *,
    session_id: UUID | None,
    cancel_close_step_type: str,
    append_step_marker: Callable[[UUID, str], Awaitable[None]],
    send_ack: bool,
    guard_send: Callable[[dict[str, Any]], Awaitable[None]],
    build_cancel_close_ok_message: Callable[[], dict[str, Any]],
    logger: logging.Logger,
) -> bool:
    try:
        if session_id is None:
            raise ValueError("session_id is required")
        await append_step_marker(session_id, cancel_close_step_type)
    except Exception as exc:
        logger.warning("WS cancel_close marker failed | %s", safe_str(exc))
        if send_ack:
            await guard_send({"type": "error", "message": "cancel_close_failed"})
        return False

    if send_ack:
        await guard_send(build_cancel_close_ok_message())
    return True
