from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from app.backend.core.jwt import decode_access_token
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
        logger.warning(
            "WS RAW EVENT | keys=%s txt=%r bin=%s",
            list(event.keys()),
            (event.get("text") or "")[:80],
            bool(event.get("bytes")),
        )
    except Exception:
        pass

    if event.get("type") == "websocket.disconnect":
        raise WebSocketDisconnect(event.get("code"))

    text = event.get("text")
    data = event.get("bytes")

    if text is not None:
        stripped = text.strip()

        if stripped and (stripped.startswith("{") or stripped.startswith("[")):
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict):
                    if "type" in obj:
                        return obj
                    if "user_input" in obj or "text" in obj:
                        text_value = obj.get("user_input") or obj.get("text") or ""
                        normalized = {"type": MSG_MESSAGE, "text": text_value}
                        for key in (
                            "step_type",
                            "emotion_label",
                            "topic",
                            "trigger_summary",
                            "insight_summary",
                            "max_items",
                            "access_token",
                        ):
                            if key in obj:
                                normalized[key] = obj[key]
                        return normalized
            except Exception:
                if strict_json:
                    raise InvalidPayload("invalid_json")

        lowered = stripped.lower()
        if lowered == MSG_PING:
            return {"type": MSG_PING}
        if lowered == MSG_OPEN:
            return {"type": MSG_OPEN}
        if lowered == MSG_CLOSE:
            return {"type": MSG_CLOSE}
        if lowered == MSG_CONFIRM_CLOSE:
            return {"type": MSG_CONFIRM_CLOSE}
        if lowered == MSG_CANCEL_CLOSE:
            return {"type": MSG_CANCEL_CLOSE}

        if "=" in stripped and "&" in stripped:
            try:
                query = parse_qs(stripped, keep_blank_values=True)
                obj = {key: (value[0] if isinstance(value, list) and value else value) for key, value in query.items()}
                if "type" in obj:
                    return obj
            except Exception:
                pass

        return {"type": MSG_MESSAGE, "text": stripped}

    if data is not None:
        raise InvalidPayload("binary_frames_not_allowed")

    return None
