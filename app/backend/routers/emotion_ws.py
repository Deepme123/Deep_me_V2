# app/routers/emotion_ws.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlmodel import Session
from uuid import UUID
import asyncio
import logging
import os
from contextlib import suppress
from typing import Callable, TypeVar

from sqlalchemy.exc import IntegrityError
from app.backend.db.session import session_scope  # 컨텍스트 매니저 사용
from app.backend.schemas.emotion import (
    ConfirmCloseRequest,
    EmotionOpenRequest,
    EmotionOpenResponse,
    EmotionMessageRequest,
    EmotionMessageResponse,
    EmotionCloseRequest,
    TaskRecommendRequest,
    TaskRecommendResponse,
)
from app.backend.services.llm_service import get_backend_llm_info, stream_noa_response
from app.backend.services.ws_protocol import (
    MSG_CANCEL_CLOSE,
    MSG_CLOSE,
    MSG_CONFIRM_CLOSE,
    MSG_MESSAGE,
    MSG_OPEN,
    MSG_PING,
    MSG_PONG,
    MSG_TASK_RECOMMEND,
    IdleTimeout as ProtocolIdleTimeout,
    InvalidPayload as ProtocolInvalidPayload,
    decode_user_id_from_token as protocol_decode_user_id_from_token,
    extract_bearer_token as protocol_extract_bearer_token,
    extract_cookie_token as protocol_extract_cookie_token,
    extract_token_fallback as protocol_extract_token_fallback,
    ws_recv_safe as protocol_ws_recv_safe,
)
from app.backend.services.ws_post_actions import (
    enter_close_cooldown as post_action_enter_close_cooldown,
    finalize_close as post_action_finalize_close,
    generate_analysis_card_async as post_action_generate_analysis_card_async,
    recommend_tasks_async as post_action_recommend_tasks_async,
)
from app.backend.services.ws_session_service import (
    append_step_marker as session_append_step_marker,
    close_session_record as session_close_session_record,
    commit_full_turn as session_commit_full_turn,
    create_emotion_session as session_create_emotion_session,
    prepare_message_context as session_prepare_message_context,
    with_db as session_with_db,
)
from app.backend.services.ws_streaming import (
    OutboundWSChannel,
    ws_send_safe as streaming_ws_send_safe,
)
from app.backend.services.stream_bridge import iter_chunks_async
from app.backend.services.ws_utils import (
    LeakGuard as SharedLeakGuard,
    mask_preview,
    safe_str,
)
from app.backend.services.web_test_user import resolve_emotion_user_id
from app.backend.core.prompt_loader import get_system_prompt, get_task_prompt
from app.backend.services.convo_policy import is_activity_turn  # test patch point
from app.backend.services.close_policy import (
    CANCEL_CLOSE_STEP_TYPE,
    RESERVED_CONFIRM_CLOSE_TOKEN,
    build_cancel_close_ok_message,
    extract_end_session_marker,
)

logger = logging.getLogger(__name__)
router = APIRouter()
ws_router = router
__all__ = ["ws_router", "router"]

# ──────────────────────────────────────────────────────────────────────────────
# 설정/상수

class WSConfig:
    SESSION_MAX_TURNS: int = int(os.getenv("SESSION_MAX_TURNS", "20"))
    WS_IDLE_TIMEOUT: float = float(os.getenv("WS_IDLE_TIMEOUT", "120"))
    WS_SEND_BUFFER: int = int(os.getenv("WS_SEND_BUFFER", "20"))
    WS_HEARTBEAT_SEC: float = float(os.getenv("WS_HEARTBEAT_SEC", "15"))
    LLM_STREAM_TIMEOUT: float = float(os.getenv("LLM_STREAM_TIMEOUT", "75"))
    RECOMMEND_TIMEOUT: float = float(os.getenv("RECOMMEND_TIMEOUT", "15"))
    ANALYSIS_CARD_TIMEOUT: float = float(os.getenv("ANALYSIS_CARD_TIMEOUT", "45"))
    WS_HISTORY_TURNS: int = max(5, min(10, int(os.getenv("WS_HISTORY_TURNS", "8"))))
    WS_MAX_USER_TEXT_LEN: int = int(os.getenv("WS_MAX_USER_TEXT_LEN", str(8 * 1024)))  # bytes/ASCII-ish

CFG = WSConfig()

T = TypeVar("T")

class TurnLimitReached(Exception):
    """Raised when a session has reached the configured turn limit."""

class SendBackpressure(Exception):
    """Raised when websocket send queue is saturated."""

async def _with_db(fn: Callable[[Session], T], *args, **kwargs) -> T:
    return await session_with_db(fn, *args, **kwargs)

async def _ws_send_safe(websocket: WebSocket, data: dict, *, timeout: float | None = None) -> None:
    await streaming_ws_send_safe(
        websocket,
        data,
        timeout=timeout,
        logger=logger,
    )

def _create_emotion_session(db: Session, uid_val: UUID | None) -> object:
    return session_create_emotion_session(db, uid_val)

def _prepare_message_context(
    db: Session,
    session_id: UUID,
    user_text: str,
    *,
    already_fired: bool | None = None,
) -> dict:
    return session_prepare_message_context(
        db,
        session_id,
        user_text,
        ws_history_turns=CFG.WS_HISTORY_TURNS,
        already_fired=already_fired,
    )

def _commit_full_turn(
    db: Session,
    session_id: UUID,
    user_text: str,
    assistant_text: str,
    user_order: int,
    assistant_order: int,
    *,
    add_activity_marker: bool,
) -> None:
    session_commit_full_turn(
        db,
        session_id,
        user_text,
        assistant_text,
        user_order,
        assistant_order,
        add_activity_marker=add_activity_marker,
    )

def _close_session_record(db: Session, session_id: UUID, payload: EmotionCloseRequest) -> None:
    session_close_session_record(db, session_id, payload)

def _append_step_marker(db: Session, session_id: UUID, step_type: str) -> None:
    session_append_step_marker(db, session_id, step_type)

async def _recommend_tasks_async(session_id: UUID, max_items: int) -> list[dict]:
    return await post_action_recommend_tasks_async(session_id, max_items)

async def _generate_analysis_card_async(session_id: UUID) -> dict:
    return await post_action_generate_analysis_card_async(session_id)

# ──────────────────────────────────────────────────────────────────────────────
# 라우터

@router.websocket("/ws/emotion")
async def ws_emotion(websocket: WebSocket):
    # Pre-accept JWT validation (header/query)
    raw_token = (
        protocol_extract_bearer_token(websocket)
        or protocol_extract_token_fallback(websocket)
        or protocol_extract_cookie_token(websocket)
    )
    auth_user_id = protocol_decode_user_id_from_token(raw_token)
    if raw_token and not auth_user_id:
        await websocket.close(code=4401, reason="invalid_token")
        return
    try:
        with session_scope() as db:
            auth_user_id = resolve_emotion_user_id(db, auth_user_id)
    except HTTPException:
        await websocket.close(code=4401, reason="auth_required")
        return
    except Exception:
        await websocket.close(code=1011, reason="auth_resolve_failed")
        return

    subproto = websocket.headers.get("sec-websocket-protocol")
    await websocket.accept(subprotocol=subproto if subproto else None)

    session_id: UUID | None = None
    leak_guard = SharedLeakGuard()
    sys_fp: set[int] = set()
    shutdown = asyncio.Event()
    recommend_fuse_tripped = False
    activity_fired: bool = False

    async def close_ws(code: int = 1000, reason: str = "") -> None:
        if shutdown.is_set():
            return
        shutdown.set()
        with suppress(Exception):
            await websocket.close(code=code, reason=reason)

    outbound = OutboundWSChannel(
        websocket=websocket,
        heartbeat_sec=CFG.WS_HEARTBEAT_SEC,
        send_buffer=CFG.WS_SEND_BUFFER,
        shutdown=shutdown,
        logger=logger,
        close_ws=close_ws,
        send_backpressure_error=SendBackpressure,
        ping_message={"type": MSG_PING},
    )

    async def guard_send(data: dict):
        await outbound.guard_send(data)

    async def flush_outbound_messages() -> None:
        await outbound.flush()

    async def _close_session_record_async(session_id_arg: UUID, payload: EmotionCloseRequest) -> None:
        await _with_db(_close_session_record, session_id_arg, payload)

    async def _append_step_marker_async(session_id_arg: UUID, step_type: str) -> None:
        await _with_db(_append_step_marker, session_id_arg, step_type)

    async def finalize_close(
        payload: EmotionCloseRequest,
        *,
        trigger_analysis_card: bool = False,
    ) -> bool:
        return await post_action_finalize_close(
            session_id=session_id,
            payload=payload,
            trigger_analysis_card=trigger_analysis_card,
            close_session_record=_close_session_record_async,
            flush_outbound_messages=flush_outbound_messages,
            send_immediate=lambda data: _ws_send_safe(websocket, data),
            generate_analysis_card=_generate_analysis_card_async,
            analysis_card_timeout=CFG.ANALYSIS_CARD_TIMEOUT,
            logger=logger,
        )

    async def enter_close_cooldown(*, send_ack: bool) -> bool:
        return await post_action_enter_close_cooldown(
            session_id=session_id,
            cancel_close_step_type=CANCEL_CLOSE_STEP_TYPE,
            append_step_marker=_append_step_marker_async,
            send_ack=send_ack,
            guard_send=guard_send,
            build_cancel_close_ok_message=build_cancel_close_ok_message,
            logger=logger,
        )

    send_task = asyncio.create_task(outbound.sender())

    # ── 연결 직후 인증된 사용자 기준으로 세션 자동 오픈
    async def _bootstrap_open_if_possible():
        nonlocal session_id, sys_fp, auth_user_id
        try:
            uid = auth_user_id
            if not uid:
                return False

            # user 존재 검증 (없으면 중단)
            try:
                from app.backend.models.user import User  # 지연 import로 순환참조 방지
            except Exception:
                User = None  # type: ignore

            if uid and User:
                user_exists = await _with_db(lambda db: db.get(User, uid) is not None)
                if not user_exists:
                    logger.warning("bootstrap: user not found | user_id=%s", uid)
                    await websocket.close(code=4401, reason="user_not_found")
                    return

            try:
                session = await _with_db(_create_emotion_session, uid)
            except IntegrityError as ie:
                logger.warning("bootstrap commit FK failed; retrying as anonymous | %s", safe_str(ie))
                session = await _with_db(_create_emotion_session, None)

            session_id = session.session_id  # ← 세션 아이디 보관

            system_prompt = get_system_prompt()
            sys_fp = leak_guard.fingerprint(system_prompt)
            await guard_send(
                EmotionOpenResponse(type="open_ok", session_id=session_id, turns=0).model_dump(),
            )
            llm_info = get_backend_llm_info()
            logger.info(
                "WS connected | session_id=%s user_id=%s provider=%s model=%s",
                session_id,
                uid,
                llm_info.provider,
                llm_info.model,
            )
            logger.info("WS bootstrap open_ok sent | session_id=%s", session_id)
        except Exception:
            logger.exception("WS bootstrap open failed")
            await close_ws(code=1011, reason="bootstrap_failed")
            return False
        return True

    # Auth token is required; bootstrap immediately.
    ok = await _bootstrap_open_if_possible()
    if not ok:
        with suppress(Exception):
            send_task.cancel()
            await asyncio.gather(send_task, return_exceptions=True)
        return

    try:
        while not shutdown.is_set():
            # 수신을 먼저 기다림
            try:
                msg = await protocol_ws_recv_safe(
                    websocket,
                    timeout=CFG.WS_IDLE_TIMEOUT,
                    raise_on_timeout=True,
                    strict_json=True,
                )
            except ProtocolIdleTimeout:
                await guard_send({"type": "error", "message": "idle_timeout"})
                break
            except WebSocketDisconnect:
                break
            except ProtocolInvalidPayload as e:
                await guard_send({"type": "error", "message": str(e)})
                await close_ws(code=1007, reason=str(e))
                break
            except Exception as e:
                logger.warning("WS recv failed | %s", safe_str(e))
                await guard_send({"type": "error", "message": "recv_failed"})
                break
            if msg is None or shutdown.is_set():
                continue

            # 파싱된 메시지 타입 로깅
            try:
                logger.warning("WS PARSED | %s", msg.get("type"))
            except Exception:
                pass

            typ = msg.get("type")

            if typ == MSG_PING:
                await guard_send({"type": MSG_PONG})
                continue

            # ── 세션 열기
            if typ == MSG_OPEN:
                if not auth_user_id:
                    await guard_send({"type": "error", "message": "auth_required"})
                    await close_ws(code=4401, reason="auth_required")
                    break

                if session_id:
                    await guard_send(EmotionOpenResponse(
                        type="open_ok",
                        session_id=session_id,
                        turns=0,
                    ).model_dump())
                    continue
                try:
                    payload = EmotionOpenRequest(**msg)
                except Exception as e:
                    await guard_send({"type": "error", "message": f"bad open payload: {e}"})
                    continue

                uid = auth_user_id

                try:
                    session = await _with_db(_create_emotion_session, uid)
                except IntegrityError as ie:
                    logger.warning("open commit FK failed; retrying anonymous | %s", safe_str(ie))
                    session = await _with_db(_create_emotion_session, None)

                session_id = session.session_id

                system_prompt = get_system_prompt()
                sys_fp = leak_guard.fingerprint(system_prompt)

                await guard_send(EmotionOpenResponse(
                    type="open_ok",
                    session_id=session_id,
                    turns=0,
                ).model_dump())

            # ── 사용자 메시지 처리
            elif typ == MSG_MESSAGE:
                if not session_id:
                    await guard_send({"type": "error", "message": "no session"})
                    continue

                try:
                    payload = EmotionMessageRequest(**msg)
                except Exception as e:
                    await guard_send({"type": "error", "message": f"bad message payload: {e}"})
                    continue

                user_text = payload.text or ""
                if len(user_text.encode("utf-8")) > CFG.WS_MAX_USER_TEXT_LEN:
                    await guard_send({"type": "error", "message": "message_too_large"})
                    continue
                logger.info("WS recv user | %s", mask_preview(user_text, 100))

                # MARK A: DB 조회 직전
                logger.warning("WS MARK A | before DB fetch")

                try:
                    prep = await _with_db(
                        _prepare_message_context,
                        session_id,
                        user_text,
                        already_fired=activity_fired,
                    )
                    transcript_rows = prep.get("transcript_rows") or prep.get("steps") or []
                    want_activity = bool(prep.get("want_activity"))
                    user_order = int(prep.get("user_order") or 0)
                    assistant_order = int(prep.get("assistant_order") or 0)
                    convo = prep.get("conversation") or []
                except TurnLimitReached:
                    await guard_send({"type": "limit", "message": "max turns reached"})
                    continue
                except Exception as e:
                    logger.exception("WS DB fetch failed")
                    await guard_send({"type": "error", "message": f"db_failed: {safe_str(e)}"})
                    continue

                # MARK B: DB 조회 통과
                logger.warning("WS MARK B | after DB fetch, before prompt")

                # 프롬프트 로딩 + MARK C
                try:
                    system_prompt = get_system_prompt()
                    task_prompt = get_task_prompt() if want_activity else None
                except Exception as e:
                    logger.exception("WS prompt load failed")
                    await guard_send({"type": "error", "message": f"prompt_failed: {safe_str(e)}"})
                    continue

                logger.warning("WS MARK C | after prompt load, before stream")

                # 스트리밍 호출 + 누적 버퍼
                assistant_chunks: list[str] = []
                token_tail_buffer = ""
                token_holdback = max(0, len(RESERVED_CONFIRM_CLOSE_TOKEN) - 1)
                stream_piece_count = 0
                end_by_token = False
                _BATCH_CHARS = 60  # 이 크기를 넘으면 WebSocket으로 즉시 flush

                async def _flush_batch(buf: str) -> None:
                    safe = leak_guard.sanitize_out(buf, sys_fp)
                    if not safe:
                        return
                    assistant_chunks.append(safe)
                    logger.debug("WS delta | %s", mask_preview(safe))
                    await guard_send(EmotionMessageResponse(type="message_delta", delta=safe).model_dump())

                async def _consume_stream():
                    nonlocal token_tail_buffer, stream_piece_count, end_by_token
                    batch_buf = ""
                    async for piece in iter_chunks_async(
                        stream_noa_response(
                            system_prompt=system_prompt,
                            task_prompt=task_prompt,
                            conversation=convo,
                            temperature=0.7,
                            max_tokens=800,
                        )
                    ):
                        stream_piece_count += 1
                        token_tail_buffer += piece
                        if stream_piece_count == 1:
                            continue
                        emit_raw = token_tail_buffer
                        if token_holdback:
                            emit_raw = token_tail_buffer[:-token_holdback]
                            token_tail_buffer = token_tail_buffer[-token_holdback:]
                        else:
                            token_tail_buffer = ""
                        if not emit_raw:
                            continue
                        batch_buf += emit_raw
                        if len(batch_buf) >= _BATCH_CHARS:
                            await _flush_batch(batch_buf)
                            batch_buf = ""

                    # 루프 종료 후 배치 잔여분 flush
                    if batch_buf:
                        await _flush_batch(batch_buf)

                    final_piece, end_by_token = extract_end_session_marker(token_tail_buffer)
                    safe_final_piece = leak_guard.sanitize_out(final_piece, sys_fp)
                    if not safe_final_piece:
                        return
                    assistant_chunks.append(safe_final_piece)
                    logger.debug("WS delta | %s", mask_preview(safe_final_piece))
                    await guard_send(
                        EmotionMessageResponse(type="message_delta", delta=safe_final_piece).model_dump()
                    )

                stream_failed_reason: str | None = None
                await guard_send(EmotionMessageResponse(type="message_start").model_dump())
                try:
                    await asyncio.wait_for(_consume_stream(), timeout=CFG.LLM_STREAM_TIMEOUT)
                except asyncio.TimeoutError:
                    stream_failed_reason = "stream_timeout"
                except Exception as e:
                    stream_failed_reason = f"stream_failed:{safe_str(e)}"
                finally:
                    await guard_send(EmotionMessageResponse(type="message_end").model_dump())

                if stream_failed_reason:
                    await guard_send({"type": "error", "message": stream_failed_reason, "turn_dropped": True})
                    continue

                assistant_text = "".join(assistant_chunks).strip()
                if not assistant_text:
                    # 내용이 비면 저장하지 않고 종료
                    await guard_send({"type": "error", "message": "empty_assistant_response", "turn_dropped": True})
                    continue

                # ② 사용자/어시스턴트 스텝을 한 트랜잭션으로 커밋
                try:
                    await _with_db(
                        _commit_full_turn,
                        session_id,
                        user_text,
                        assistant_text,
                        user_order,
                        assistant_order,
                        add_activity_marker=want_activity,
                    )
                except TurnLimitReached:
                    await guard_send({"type": "limit", "message": "max turns reached"})
                    continue
                except Exception:
                    logger.exception("WS assistant-step commit failed")
                    await guard_send({"type": "error", "message": "server_error:assistant_step_commit"})
                    continue

                if want_activity:
                    activity_fired = True

                await guard_send(
                    EmotionMessageResponse(
                        type="message",
                        message=assistant_text,
                    ).model_dump()
                )

                if end_by_token:
                    payload = EmotionCloseRequest()
                    if await finalize_close(payload, trigger_analysis_card=True):
                        break
                    continue

                if want_activity:
                    if recommend_fuse_tripped:
                        await guard_send({"type": "error", "message": "recommend_unavailable"})
                    else:
                        try:
                            items = await asyncio.wait_for(
                                _recommend_tasks_async(session_id, 5),
                                timeout=CFG.RECOMMEND_TIMEOUT,
                            )
                        except Exception as e:
                            recommend_fuse_tripped = True
                            logger.warning("task recommend failed | %s", safe_str(e))
                            await guard_send({"type": "error", "message": "recommend_unavailable"})
                        else:
                            if items:
                                await guard_send(
                                    TaskRecommendResponse(
                                        type="task_recommend_ok",
                                        items=items,
                                    ).model_dump()
                                )

            # ── 세션 종료
            elif typ == MSG_CLOSE:
                if not session_id:
                    await guard_send({"type": "error", "message": "no session"})
                    continue

                try:
                    payload = EmotionCloseRequest(**msg)
                except Exception as e:
                    await guard_send({"type": "error", "message": f"bad close payload: {e}"})
                    continue

                if await finalize_close(payload):
                    break

            elif typ == MSG_CONFIRM_CLOSE:
                if not session_id:
                    await guard_send({"type": "error", "message": "no session"})
                    continue

                try:
                    ConfirmCloseRequest(**msg)
                    payload = EmotionCloseRequest(
                        emotion_label=msg.get("emotion_label"),
                        topic=msg.get("topic"),
                        trigger_summary=msg.get("trigger_summary"),
                        insight_summary=msg.get("insight_summary"),
                    )
                except Exception as e:
                    await guard_send({"type": "error", "message": f"bad confirm close payload: {e}"})
                    continue

                if await finalize_close(payload, trigger_analysis_card=True):
                    break

            elif typ == MSG_CANCEL_CLOSE:
                if not session_id:
                    await guard_send({"type": "error", "message": "no session"})
                    continue

                await enter_close_cooldown(send_ack=True)

            # ── 태스크 추천
            elif typ == MSG_TASK_RECOMMEND:
                if not session_id:
                    await guard_send({"type": "error", "message": "no session"})
                    continue

                try:
                    payload = TaskRecommendRequest(**msg)
                except Exception as e:
                    await guard_send({"type": "error", "message": f"bad task payload: {e}"})
                    continue

                if recommend_fuse_tripped:
                    await guard_send({"type": "error", "message": "recommend_unavailable"})
                    continue

                try:
                    recs = await asyncio.wait_for(
                        _recommend_tasks_async(session_id, payload.max_items or 5),
                        timeout=CFG.RECOMMEND_TIMEOUT,
                    )
                except Exception as e:
                    recommend_fuse_tripped = True
                    logger.error("task recommend failed | %s", safe_str(e))
                    await guard_send({"type": "error", "message": f"recommend failed: {safe_str(e)}"})
                    continue

                await guard_send(TaskRecommendResponse(
                    type="task_recommend_ok",
                    items=recs,
                ).model_dump())

            else:
                await guard_send({"type": "error", "message": f"unknown type: {typ}"})

    except WebSocketDisconnect:
        shutdown.set()
    except SendBackpressure:
        logger.warning("WS closed due to send backpressure")
    except Exception:
        logger.exception("WS fatal error")
        with suppress(Exception):
            await _ws_send_safe(websocket, {"type": "error", "message": "fatal"})
    finally:
        shutdown.set()
        with suppress(Exception):
            send_task.cancel()
            await asyncio.gather(send_task, return_exceptions=True)
        with suppress(Exception):
            await websocket.close()
