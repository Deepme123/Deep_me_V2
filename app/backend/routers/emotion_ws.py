# app/routers/emotion_ws.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlmodel import Session
from uuid import UUID
import asyncio
import logging
import os
import random
from contextlib import suppress

from sqlalchemy.exc import IntegrityError
from app.db.session import session_scope  # 컨텍스트 매니저 사용
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
    commit_opening_message as session_commit_opening_message,
    create_emotion_session as session_create_emotion_session,
    prepare_message_context as session_prepare_message_context,
    with_db as session_with_db,
)
from app.backend.services.greeting_service import (
    pick_greeting_message as greeting_pick_greeting_message,
)
from app.backend.core.greeting_loader import (
    get_greeting_messages as greeting_get_greeting_messages,
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
    StreamingConfirmCloseFilter,
    build_cancel_close_ok_message,
)

logger = logging.getLogger(__name__)
router = APIRouter()
ws_router = router
__all__ = ["ws_router", "router"]

# ──────────────────────────────────────────────────────────────────────────────
# 설정/상수

class WSConfig:
    SESSION_MAX_TURNS: int = int(os.getenv("SESSION_MAX_TURNS", "20"))
    WS_IDLE_TIMEOUT: float = float(os.getenv("WS_IDLE_TIMEOUT", "600"))
    WS_SEND_BUFFER: int = int(os.getenv("WS_SEND_BUFFER", "50"))
    WS_HEARTBEAT_SEC: float = float(os.getenv("WS_HEARTBEAT_SEC", "30"))
    LLM_STREAM_TIMEOUT: float = float(os.getenv("LLM_STREAM_TIMEOUT", "120"))
    RECOMMEND_TIMEOUT: float = float(os.getenv("RECOMMEND_TIMEOUT", "15"))
    # 분석카드 생성 LLM(get_card_provider) 자체 timeout이 LLM_TIMEOUT_SEC
    # 기본값(60초)이므로, 이 값이 그보다 작으면 LLM 응답을 기다리는 도중에
    # asyncio.wait_for가 먼저 만료되어 정상 응답도 TimeoutError로 실패 처리된다.
    # DB 조회/직렬화 오버헤드까지 감안해 60초보다 여유 있게 설정한다.
    ANALYSIS_CARD_TIMEOUT: float = float(os.getenv("ANALYSIS_CARD_TIMEOUT", "75"))
    WS_HISTORY_TURNS: int = max(5, min(10, int(os.getenv("WS_HISTORY_TURNS", "8"))))
    WS_MAX_USER_TEXT_LEN: int = int(os.getenv("WS_MAX_USER_TEXT_LEN", str(8 * 1024)))  # bytes/ASCII-ish
    # [[CONFIRM_CLOSE]] 토큰은 STEP 12(마무리)에서만 나와야 함.
    # user_order가 이 값 미만이면 토큰이 감지돼도 세션 종료를 억제한다.
    # 12단계 대화 기준 최소 user_order ≈ 23 이므로 16을 기본값으로 사용.
    MIN_CLOSE_ORDER: int = int(os.getenv("MIN_CLOSE_ORDER", "16"))
    # 세션 오픈 직후 서버가 먼저 인사 메시지를 보내기 전 대기하는 시간(초).
    # 곧바로 뜨는 느낌보다 자연스러운 텀을 주기 위함.
    GREETING_DELAY_MIN_SEC: float = float(os.getenv("GREETING_DELAY_MIN_SEC", "1.0"))
    GREETING_DELAY_MAX_SEC: float = float(os.getenv("GREETING_DELAY_MAX_SEC", "2.0"))

CFG = WSConfig()

class TurnLimitReached(Exception):
    """Raised when a session has reached the configured turn limit."""

class SendBackpressure(Exception):
    """Raised when websocket send queue is saturated."""

# ──────────────────────────────────────────────────────────────────────────────
# 연결 핸들러
#
# 연결 하나(WebSocket 하나)의 생명주기 전체(인증→accept→오프닝 인사→메시지
# 루프→종료)를 담당한다. 이전에는 이 상태(session_id, leak_guard 등)를 라우터
# 함수 안의 nonlocal 클로저로 들고 있었는데, 메서드 단위로 쪼개 가독성을
# 높이기 위해 인스턴스 상태로 옮겼다. 모듈 최상위에 import된 이름들
# (session_with_db, get_system_prompt, CFG 등)은 테스트가 monkeypatch로
# 직접 오버라이드하는 지점이라 그대로 자유 함수 호출 형태로 남겨뒀다.


class _EmotionWSHandler:
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.session_id: UUID | None = None
        self.leak_guard = SharedLeakGuard()
        self.sys_fp: set[int] = set()
        self.shutdown = asyncio.Event()
        self.recommend_fuse_tripped = False
        self.activity_fired = False
        self.auth_user_id = None
        self.outbound: OutboundWSChannel | None = None
        self.send_task: asyncio.Task | None = None

    # ── 저수준 송신/종료 ────────────────────────────────────────────────

    async def close_ws(self, code: int = 1000, reason: str = "") -> None:
        if self.shutdown.is_set():
            return
        self.shutdown.set()
        with suppress(Exception):
            await self.websocket.close(code=code, reason=reason)

    async def guard_send(self, data: dict) -> None:
        await self.outbound.guard_send(data)

    async def flush_outbound_messages(self) -> None:
        await self.outbound.flush()

    async def _close_session_record_async(
        self, session_id_arg: UUID, payload: EmotionCloseRequest
    ) -> None:
        await session_with_db(session_close_session_record, session_id_arg, payload)

    async def _append_step_marker_async(self, session_id_arg: UUID, step_type: str) -> None:
        await session_with_db(session_append_step_marker, session_id_arg, step_type)

    async def finalize_close(
        self,
        payload: EmotionCloseRequest,
        *,
        trigger_analysis_card: bool = False,
    ) -> bool:
        return await post_action_finalize_close(
            session_id=self.session_id,
            payload=payload,
            trigger_analysis_card=trigger_analysis_card,
            close_session_record=self._close_session_record_async,
            flush_outbound_messages=self.flush_outbound_messages,
            send_immediate=lambda data: streaming_ws_send_safe(self.websocket, data, logger=logger),
            generate_analysis_card=post_action_generate_analysis_card_async,
            analysis_card_timeout=CFG.ANALYSIS_CARD_TIMEOUT,
            logger=logger,
        )

    async def enter_close_cooldown(self, *, send_ack: bool) -> bool:
        return await post_action_enter_close_cooldown(
            session_id=self.session_id,
            cancel_close_step_type=CANCEL_CLOSE_STEP_TYPE,
            append_step_marker=self._append_step_marker_async,
            send_ack=send_ack,
            guard_send=self.guard_send,
            build_cancel_close_ok_message=build_cancel_close_ok_message,
            logger=logger,
        )

    # ── 사용자 메시지(MSG_MESSAGE) 처리 ────────────────────────────────

    async def handle_message(self, msg: dict) -> bool:
        """MSG_MESSAGE 처리. True 반환 시 루프 종료."""
        if not self.session_id:
            await self.guard_send({"type": "error", "message": "no session"})
            return False

        try:
            payload = EmotionMessageRequest(**msg)
        except Exception as e:
            await self.guard_send({"type": "error", "message": f"bad message payload: {e}"})
            return False

        user_text = payload.text or ""
        if len(user_text.encode("utf-8")) > CFG.WS_MAX_USER_TEXT_LEN:
            await self.guard_send({"type": "error", "message": "message_too_large"})
            return False
        logger.info("WS recv user | %s", mask_preview(user_text, 100))

        try:
            prep = await session_with_db(
                lambda db: session_prepare_message_context(
                    db,
                    self.session_id,
                    user_text,
                    ws_history_turns=CFG.WS_HISTORY_TURNS,
                    already_fired=self.activity_fired,
                )
            )
            want_activity = bool(prep.get("want_activity"))
            user_order = int(prep.get("user_order") or 0)
            assistant_order = int(prep.get("assistant_order") or 0)
            convo = prep.get("conversation") or []
        except TurnLimitReached:
            await self.guard_send({"type": "limit", "message": "max turns reached"})
            return False
        except Exception as e:
            logger.exception("WS DB fetch failed")
            await self.guard_send({"type": "error", "message": f"db_failed: {safe_str(e)}"})
            return False

        try:
            system_prompt = get_system_prompt()
            task_prompt = get_task_prompt() if want_activity else None
        except Exception as e:
            logger.exception("WS prompt load failed")
            await self.guard_send({"type": "error", "message": f"prompt_failed: {safe_str(e)}"})
            return False

        assistant_chunks: list[str] = []
        close_filter = StreamingConfirmCloseFilter()
        end_by_token = False
        _BATCH_CHARS = 60

        async def _flush_batch(buf: str) -> None:
            safe = self.leak_guard.sanitize_out(buf, self.sys_fp)
            if not safe:
                return
            assistant_chunks.append(safe)
            logger.debug("WS delta | %s", mask_preview(safe))
            await self.guard_send(EmotionMessageResponse(type="message_delta", delta=safe).model_dump())

        async def _consume_stream():
            nonlocal end_by_token
            batch_buf = ""
            async for piece in iter_chunks_async(
                stream_noa_response(
                    system_prompt=system_prompt,
                    task_prompt=task_prompt,
                    conversation=convo,
                    temperature=0.7,
                    max_tokens=1500,
                )
            ):
                emit_raw = close_filter.feed(piece)
                if emit_raw:
                    batch_buf += emit_raw
                    if len(batch_buf) >= _BATCH_CHARS:
                        await _flush_batch(batch_buf)
                        batch_buf = ""
                if close_filter.end_detected:
                    break

            tail = close_filter.flush()
            if tail:
                batch_buf += tail
            if batch_buf:
                await _flush_batch(batch_buf)
            end_by_token = close_filter.end_detected

        stream_failed_reason: str | None = None
        await self.guard_send(EmotionMessageResponse(type="message_start").model_dump())
        try:
            await asyncio.wait_for(_consume_stream(), timeout=CFG.LLM_STREAM_TIMEOUT)
        except asyncio.TimeoutError:
            stream_failed_reason = "stream_timeout"
        except Exception as e:
            stream_failed_reason = f"stream_failed:{safe_str(e)}"
        finally:
            await self.guard_send(EmotionMessageResponse(type="message_end").model_dump())

        if stream_failed_reason:
            await self.guard_send({"type": "error", "message": stream_failed_reason, "turn_dropped": True})
            return False

        # [[CONFIRM_CLOSE]]는 STEP 12(마무리)에서만 유효.
        # 너무 이른 단계에서 감지되면 LLM 오발생으로 판단해 세션 종료를 억제한다.
        if end_by_token and user_order < CFG.MIN_CLOSE_ORDER:
            logger.warning(
                "WS [[CONFIRM_CLOSE]] suppressed at early turn | user_order=%s min=%s",
                user_order,
                CFG.MIN_CLOSE_ORDER,
            )
            end_by_token = False

        assistant_text = "".join(assistant_chunks).strip()
        if not assistant_text:
            await self.guard_send({"type": "error", "message": "empty_assistant_response", "turn_dropped": True})
            return False

        try:
            await session_with_db(
                session_commit_full_turn,
                self.session_id,
                user_text,
                assistant_text,
                user_order,
                assistant_order,
                add_activity_marker=want_activity,
            )
        except TurnLimitReached:
            await self.guard_send({"type": "limit", "message": "max turns reached"})
            return False
        except Exception:
            logger.exception("WS assistant-step commit failed")
            await self.guard_send({"type": "error", "message": "server_error:assistant_step_commit"})
            return False

        if want_activity:
            self.activity_fired = True

        await self.guard_send(
            EmotionMessageResponse(type="message", message=assistant_text).model_dump()
        )

        if end_by_token:
            close_payload = EmotionCloseRequest()
            return await self.finalize_close(close_payload, trigger_analysis_card=True)

        if want_activity:
            if self.recommend_fuse_tripped:
                await self.guard_send({"type": "error", "message": "recommend_unavailable"})
            else:
                try:
                    items = await asyncio.wait_for(
                        post_action_recommend_tasks_async(self.session_id, 5),
                        timeout=CFG.RECOMMEND_TIMEOUT,
                    )
                except Exception as e:
                    self.recommend_fuse_tripped = True
                    logger.warning("task recommend failed | %s", safe_str(e))
                    await self.guard_send({"type": "error", "message": "recommend_unavailable"})
                else:
                    if items:
                        await self.guard_send(
                            TaskRecommendResponse(type="task_recommend_ok", items=items).model_dump()
                        )

        return False

    # ── 세션 오픈 직후, 사용자 입력 없이 서버가 먼저 인사 메시지를 보냄 ──

    async def send_opening_greeting(self) -> None:
        # DB 기반 선택(카운터 조회/증가)이 실패해도 인사말 자체는 항상 나가야 하므로,
        # 실패 시 DB에 의존하지 않는 무작위 선택으로 폴백한다.
        try:
            _, greeting_text = await session_with_db(greeting_pick_greeting_message)
        except Exception:
            logger.exception(
                "WS opening greeting selection failed, falling back to random pick | session_id=%s",
                self.session_id,
            )
            try:
                greeting_text = random.choice(greeting_get_greeting_messages())
            except Exception:
                logger.exception(
                    "WS opening greeting fallback pick failed | session_id=%s", self.session_id
                )
                return

        delay = random.uniform(CFG.GREETING_DELAY_MIN_SEC, CFG.GREETING_DELAY_MAX_SEC)
        await asyncio.sleep(delay)

        try:
            await self.guard_send(EmotionMessageResponse(type="message_start").model_dump())
            await self.guard_send(
                EmotionMessageResponse(type="message", message=greeting_text).model_dump()
            )
            await self.guard_send(EmotionMessageResponse(type="message_end").model_dump())
        except Exception:
            logger.exception("WS opening greeting send failed | session_id=%s", self.session_id)
            return

        # 클라이언트에는 이미 전달된 상태이므로, 이후 DB 커밋(기록/카운터) 실패는
        # 인사말 누락으로 이어지지 않는다 — 별도로 로그만 남긴다.
        try:
            await session_with_db(session_commit_opening_message, self.session_id, greeting_text)
        except Exception:
            logger.exception(
                "WS opening greeting commit failed (message already sent) | session_id=%s",
                self.session_id,
            )

    # ── 연결 직후 인증된 사용자 기준으로 세션 자동 오픈 ──────────────────

    async def bootstrap_open_if_possible(self) -> bool:
        try:
            uid = self.auth_user_id
            if not uid:
                return False

            # user 존재 검증 (없으면 중단)
            try:
                from app.backend.models.user import User  # 지연 import로 순환참조 방지
            except Exception:
                User = None  # type: ignore

            if uid and User:
                user_exists = await session_with_db(lambda db: db.get(User, uid) is not None)
                if not user_exists:
                    logger.warning("bootstrap: user not found | user_id=%s", uid)
                    await self.websocket.close(code=4401, reason="user_not_found")
                    return

            try:
                session = await session_with_db(session_create_emotion_session, uid)
            except IntegrityError as ie:
                logger.warning("bootstrap commit FK failed; retrying as anonymous | %s", safe_str(ie))
                session = await session_with_db(session_create_emotion_session, None)

            self.session_id = session.session_id  # ← 세션 아이디 보관

            system_prompt = get_system_prompt()
            self.sys_fp = self.leak_guard.fingerprint(system_prompt)
            await self.guard_send(
                EmotionOpenResponse(type="open_ok", session_id=self.session_id, turns=0).model_dump(),
            )
            llm_info = get_backend_llm_info()
            logger.info(
                "WS connected | session_id=%s user_id=%s provider=%s model=%s",
                self.session_id,
                uid,
                llm_info.provider,
                llm_info.model,
            )
            logger.info("WS bootstrap open_ok sent | session_id=%s", self.session_id)
            await self.send_opening_greeting()
        except Exception:
            logger.exception("WS bootstrap open failed")
            await self.close_ws(code=1011, reason="bootstrap_failed")
            return False
        return True

    # ── 메시지 타입별 디스패치 ────────────────────────────────────────

    async def dispatch(self, msg: dict) -> bool:
        """수신 메시지 1건을 타입별로 처리한다. True 반환 시 루프 종료."""
        try:
            logger.debug("WS PARSED | %s", msg.get("type"))
        except Exception:
            pass

        typ = msg.get("type")

        if typ == MSG_PING:
            await self.guard_send({"type": MSG_PONG})
            return False

        # ── 세션 열기
        if typ == MSG_OPEN:
            if not self.auth_user_id:
                await self.guard_send({"type": "error", "message": "auth_required"})
                await self.close_ws(code=4401, reason="auth_required")
                return True

            if self.session_id:
                await self.guard_send(EmotionOpenResponse(
                    type="open_ok",
                    session_id=self.session_id,
                    turns=0,
                ).model_dump())
                return False
            try:
                EmotionOpenRequest(**msg)
            except Exception as e:
                await self.guard_send({"type": "error", "message": f"bad open payload: {e}"})
                return False

            uid = self.auth_user_id

            try:
                session = await session_with_db(session_create_emotion_session, uid)
            except IntegrityError as ie:
                logger.warning("open commit FK failed; retrying anonymous | %s", safe_str(ie))
                session = await session_with_db(session_create_emotion_session, None)

            self.session_id = session.session_id

            system_prompt = get_system_prompt()
            self.sys_fp = self.leak_guard.fingerprint(system_prompt)

            await self.guard_send(EmotionOpenResponse(
                type="open_ok",
                session_id=self.session_id,
                turns=0,
            ).model_dump())
            return False

        # ── 사용자 메시지 처리
        if typ == MSG_MESSAGE:
            return await self.handle_message(msg)

        # ── 세션 종료
        if typ == MSG_CLOSE:
            if not self.session_id:
                await self.guard_send({"type": "error", "message": "no session"})
                return False

            try:
                payload = EmotionCloseRequest(**msg)
            except Exception as e:
                await self.guard_send({"type": "error", "message": f"bad close payload: {e}"})
                return False

            return await self.finalize_close(payload)

        if typ == MSG_CONFIRM_CLOSE:
            if not self.session_id:
                await self.guard_send({"type": "error", "message": "no session"})
                return False

            try:
                ConfirmCloseRequest(**msg)
                payload = EmotionCloseRequest(
                    emotion_label=msg.get("emotion_label"),
                    topic=msg.get("topic"),
                    trigger_summary=msg.get("trigger_summary"),
                    insight_summary=msg.get("insight_summary"),
                )
            except Exception as e:
                await self.guard_send({"type": "error", "message": f"bad confirm close payload: {e}"})
                return False

            return await self.finalize_close(payload, trigger_analysis_card=True)

        if typ == MSG_CANCEL_CLOSE:
            if not self.session_id:
                await self.guard_send({"type": "error", "message": "no session"})
                return False

            await self.enter_close_cooldown(send_ack=True)
            return False

        # ── 태스크 추천
        if typ == MSG_TASK_RECOMMEND:
            if not self.session_id:
                await self.guard_send({"type": "error", "message": "no session"})
                return False

            try:
                payload = TaskRecommendRequest(**msg)
            except Exception as e:
                await self.guard_send({"type": "error", "message": f"bad task payload: {e}"})
                return False

            if self.recommend_fuse_tripped:
                await self.guard_send({"type": "error", "message": "recommend_unavailable"})
                return False

            try:
                recs = await asyncio.wait_for(
                    post_action_recommend_tasks_async(self.session_id, payload.max_items or 5),
                    timeout=CFG.RECOMMEND_TIMEOUT,
                )
            except Exception as e:
                self.recommend_fuse_tripped = True
                logger.error("task recommend failed | %s", safe_str(e))
                await self.guard_send({"type": "error", "message": f"recommend failed: {safe_str(e)}"})
                return False

            await self.guard_send(TaskRecommendResponse(
                type="task_recommend_ok",
                items=recs,
            ).model_dump())
            return False

        await self.guard_send({"type": "error", "message": f"unknown type: {typ}"})
        return False

    # ── 연결 전체 생명주기 ────────────────────────────────────────────

    async def run(self) -> None:
        websocket = self.websocket

        # Pre-accept JWT validation (header/query)
        raw_token = (
            protocol_extract_bearer_token(websocket)
            or protocol_extract_token_fallback(websocket)
            or protocol_extract_cookie_token(websocket)
        )
        self.auth_user_id = protocol_decode_user_id_from_token(raw_token)
        if raw_token and not self.auth_user_id:
            await websocket.close(code=4401, reason="invalid_token")
            return
        try:
            with session_scope() as db:
                self.auth_user_id = resolve_emotion_user_id(db, self.auth_user_id)
        except HTTPException:
            await websocket.close(code=4401, reason="auth_required")
            return
        except Exception:
            await websocket.close(code=1011, reason="auth_resolve_failed")
            return

        subproto = websocket.headers.get("sec-websocket-protocol")
        await websocket.accept(subprotocol=subproto if subproto else None)

        self.outbound = OutboundWSChannel(
            websocket=websocket,
            heartbeat_sec=CFG.WS_HEARTBEAT_SEC,
            send_buffer=CFG.WS_SEND_BUFFER,
            shutdown=self.shutdown,
            logger=logger,
            close_ws=self.close_ws,
            send_backpressure_error=SendBackpressure,
            ping_message={"type": MSG_PING},
        )

        self.send_task = asyncio.create_task(self.outbound.sender())

        # Auth token is required; bootstrap immediately.
        ok = await self.bootstrap_open_if_possible()
        if not ok:
            with suppress(Exception):
                self.send_task.cancel()
                await asyncio.gather(self.send_task, return_exceptions=True)
            return

        try:
            while not self.shutdown.is_set():
                # 수신을 먼저 기다림
                try:
                    msg = await protocol_ws_recv_safe(
                        websocket,
                        timeout=CFG.WS_IDLE_TIMEOUT,
                        raise_on_timeout=True,
                        strict_json=True,
                    )
                except ProtocolIdleTimeout:
                    await self.guard_send({"type": "error", "message": "idle_timeout"})
                    break
                except WebSocketDisconnect:
                    break
                except ProtocolInvalidPayload as e:
                    await self.guard_send({"type": "error", "message": str(e)})
                    await self.close_ws(code=1007, reason=str(e))
                    break
                except Exception as e:
                    logger.warning("WS recv failed | %s", safe_str(e))
                    await self.guard_send({"type": "error", "message": "recv_failed"})
                    break
                if msg is None or self.shutdown.is_set():
                    continue

                if await self.dispatch(msg):
                    break

        except WebSocketDisconnect:
            self.shutdown.set()
        except SendBackpressure:
            logger.warning("WS closed due to send backpressure")
        except Exception:
            logger.exception("WS fatal error")
            with suppress(Exception):
                await streaming_ws_send_safe(websocket, {"type": "error", "message": "fatal"}, logger=logger)
        finally:
            self.shutdown.set()
            with suppress(Exception):
                self.send_task.cancel()
                await asyncio.gather(self.send_task, return_exceptions=True)
            with suppress(Exception):
                await websocket.close()


# ──────────────────────────────────────────────────────────────────────────────
# 라우터

@router.websocket("/ws/emotion")
async def ws_emotion(websocket: WebSocket) -> None:
    await _EmotionWSHandler(websocket).run()
