from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from app.core.jwt import decode_access_token
from app.backend.services.close_policy import CANCEL_CLOSE_MESSAGE_TYPE
from app.backend.services.ws_utils import ensure_uuid, safe_str

logger = logging.getLogger(__name__)

MSG_OPEN = "open"
MSG_MESSAGE = "message"
MSG_CLOSE = "close"
MSG_CONFIRM_CLOSE = "confirm_close"
MSG_CANCEL_CLOSE = CANCEL_CLOSE_MESSAGE_TYPE
MSG_TASK_RECOMMEND = "task_recommend"
MSG_PING = "ping"
MSG_PONG = "pong"


class IdleTimeout(Exception):
    """Raised when websocket idle timeout hit."""


class InvalidPayload(Exception):
    """Raised when websocket payload is malformed or unsupported."""


def extract_bearer_token(websocket: WebSocket) -> str | None:
    auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if not auth_header:
        return None
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip() or None
    return None


def extract_token_fallback(websocket: WebSocket) -> str | None:
    query_params = websocket.query_params
    if query_params:
        for key in ("access_token", "token", "auth_token"):
            if query_params.get(key):
                return query_params.get(key)
    return None


def extract_cookie_token(websocket: WebSocket) -> str | None:
    cookies = getattr(websocket, "cookies", None) or {}
    return cookies.get("access_token")


def decode_user_id_from_token(token: str | None) -> UUID | None:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not isinstance(payload, dict):
        return None
    try:
        return ensure_uuid(payload.get("sub"))
    except Exception:
        return None


# 타입 없이 키워드만 보내도 해당 메시지로 인정하는 타입들
_BARE_KEYWORD_TYPES = frozenset(
    {MSG_PING, MSG_OPEN, MSG_CLOSE, MSG_CONFIRM_CLOSE, MSG_CANCEL_CLOSE}
)
# type 없는 JSON을 message로 정규화할 때 함께 넘겨주는 키
_MESSAGE_PASSTHROUGH_KEYS = (
    "step_type",
    "emotion_label",
    "topic",
    "trigger_summary",
    "insight_summary",
    "max_items",
    "access_token",
)


def _normalize_json_payload(obj: object) -> dict | None:
    """JSON 페이로드를 프로토콜 메시지로 바꾼다. 메시지로 볼 수 없으면 None."""
    if not isinstance(obj, dict):
        return None
    if "type" in obj:
        return obj
    if "user_input" not in obj and "text" not in obj:
        return None
    normalized = {"type": MSG_MESSAGE, "text": obj.get("user_input") or obj.get("text") or ""}
    normalized.update({key: obj[key] for key in _MESSAGE_PASSTHROUGH_KEYS if key in obj})
    return normalized


def _parse_query_string(stripped: str) -> dict | None:
    """`type=message&text=hi` 형태를 dict로 바꾼다. type이 없으면 None."""
    if "=" not in stripped or "&" not in stripped:
        return None
    try:
        query = parse_qs(stripped, keep_blank_values=True)
    except Exception:
        return None
    obj = {key: (value[0] if value else value) for key, value in query.items()}
    return obj if "type" in obj else None


def _parse_text_frame(text: str, *, strict_json: bool) -> dict:
    stripped = text.strip()

    if stripped.startswith(("{", "[")):
        try:
            obj = json.loads(stripped)
        except Exception:
            if strict_json:
                raise InvalidPayload("invalid_json")
        else:
            message = _normalize_json_payload(obj)
            if message is not None:
                return message

    lowered = stripped.lower()
    if lowered in _BARE_KEYWORD_TYPES:
        return {"type": lowered}

    return _parse_query_string(stripped) or {"type": MSG_MESSAGE, "text": stripped}


async def ws_recv_safe(
    websocket: WebSocket,
    *,
    timeout: float | None = None,
    raise_on_timeout: bool = False,
    strict_json: bool = True,
) -> dict | None:
    try:
        if timeout:
            event = await asyncio.wait_for(websocket.receive(), timeout=timeout)
        else:
            event = await websocket.receive()
    except asyncio.TimeoutError:
        if raise_on_timeout:
            raise IdleTimeout()
        return {"type": MSG_PING}
    except WebSocketDisconnect:
        raise
    except Exception as exc:
        logger.warning("WS recv() failed | %s", safe_str(exc))
        return None

    try:
        logger.debug(
            "WS RAW EVENT | keys=%s",
            list(event.keys()),
        )
    except Exception:
        pass

    if event.get("type") == "websocket.disconnect":
        raise WebSocketDisconnect(event.get("code"))

    text = event.get("text")
    if text is not None:
        return _parse_text_frame(text, strict_json=strict_json)

    if event.get("bytes") is not None:
        raise InvalidPayload("binary_frames_not_allowed")

    return None
