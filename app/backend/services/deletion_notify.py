"""회원탈퇴 예약/삭제 완료 Discord 알림.

탈퇴 로직(schedule_account_deletion / sweep_due_account_deletions)은 동기 코드라
async인 deploy_discord._send_discord를 못 쓴다 — logging_config.DiscordErrorHandler와
같은 방식으로 백그라운드 스레드에서 httpx.Client로 전송한다.

알림 실패가 탈퇴 로직에 영향을 주면 안 되므로 이 모듈의 공개 함수는 절대 예외를
올리지 않는다. 개인정보 보호를 위해 이메일/이름은 알림에 싣지 않고 user_id와 탈퇴
사유 코드, 시각만 보낸다.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 10
_FOOTER = {"text": "Deep Me Account Bot"}


def _handle_http_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        msgs = {
            401: "인증 실패 — API 키 확인",
            403: "권한 없음 — 토큰 권한 범위 확인",
            404: "리소스 없음 — 서비스 ID 또는 URL 확인",
            429: "Rate limit 초과 — 잠시 후 재시도",
        }
        return f"Error {code}: {msgs.get(code, e.response.text[:200])}"
    if isinstance(e, httpx.TimeoutException):
        return "Error: 요청 타임아웃"
    if isinstance(e, httpx.ConnectError):
        return "Error: 연결 실패"
    return f"Error: {type(e).__name__}: {e}"


def _webhook_url() -> str:
    # import 시점에 고정하지 않고 호출 시점에 읽는다 — 배포 env 변경/테스트 반영용.
    return os.getenv("DISCORD_DELETION_WEBHOOK_URL", "")


def _env_label() -> str:
    # Render가 서비스마다 자동으로 주입한다(deep-me-v2 / deep-me-v2-test).
    return os.getenv("RENDER_SERVICE_NAME", "local")


def _fmt(dt: datetime) -> str:
    # 탈퇴 관련 시각은 모두 naive UTC(datetime.utcnow())로 저장된다.
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _build_requested_embed(
    user_id: UUID, reason_codes: list[int], scheduled_at: datetime
) -> dict[str, Any]:
    env = _env_label()
    return {"embeds": [{
        "title": f"🚪 [{env}] 회원 탈퇴 예약",
        "description": "탈퇴 요청이 들어와서 삭제가 예약됐어.",
        "color": 0xFEE75C,
        "fields": [
            {"name": "user_id", "value": f"`{user_id}`", "inline": False},
            {"name": "탈퇴 사유 코드", "value": ", ".join(str(c) for c in reason_codes) or "-", "inline": True},
            {"name": "삭제 예정", "value": _fmt(scheduled_at), "inline": True},
        ],
        "footer": _FOOTER,
    }]}


def _build_completed_embed(
    user_id: UUID, requested_at: datetime | None, deleted_at: datetime
) -> dict[str, Any]:
    env = _env_label()
    return {"embeds": [{
        "title": f"🗑️ [{env}] 회원 데이터 삭제 완료",
        "description": "유예 기간이 지나서 스케줄러가 계정 데이터를 삭제했어.",
        "color": 0x5865F2,
        "fields": [
            {"name": "user_id", "value": f"`{user_id}`", "inline": False},
            {"name": "탈퇴 요청", "value": _fmt(requested_at) if requested_at else "-", "inline": True},
            {"name": "삭제 시각", "value": _fmt(deleted_at), "inline": True},
        ],
        "footer": _FOOTER,
    }]}


def _post(payload: dict[str, Any], webhook_url: str) -> None:
    try:
        with httpx.Client(timeout=_TIMEOUT_SEC) as client:
            resp = client.post(webhook_url, json=payload)
            resp.raise_for_status()
    except Exception as e:
        # error 레벨이면 DiscordErrorHandler가 다시 Discord로 보내려 하므로 warning으로 남긴다.
        logger.warning("탈퇴 Discord 알림 실패: %s", _handle_http_error(e))


def _dispatch(payload: dict[str, Any]) -> None:
    webhook_url = _webhook_url()
    if not webhook_url:
        return
    threading.Thread(target=_post, args=(payload, webhook_url), daemon=True).start()


def notify_deletion_requested(
    user_id: UUID, reason_codes: list[int], scheduled_at: datetime
) -> None:
    """탈퇴 예약(DELETE /me) 알림. 절대 예외를 올리지 않는다."""
    try:
        _dispatch(_build_requested_embed(user_id, reason_codes, scheduled_at))
    except Exception:
        logger.warning("탈퇴 예약 Discord 알림 준비 중 오류", exc_info=True)


def notify_deletion_completed(
    user_id: UUID, requested_at: datetime | None, deleted_at: datetime
) -> None:
    """유예 기간 만료 후 실제 삭제 완료 알림. 절대 예외를 올리지 않는다."""
    try:
        _dispatch(_build_completed_embed(user_id, requested_at, deleted_at))
    except Exception:
        logger.warning("탈퇴 완료 Discord 알림 준비 중 오류", exc_info=True)
