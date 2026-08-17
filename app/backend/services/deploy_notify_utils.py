"""배포/PR 알림 파이프라인이 공통으로 쓰는 포맷팅·에러 처리 유틸리티."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _short_sha(sha: str) -> str:
    return sha[:7] if sha else "unknown"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _safe_json(resp: httpx.Response) -> dict[str, Any]:
    """Render 응답이 2xx여도 본문이 JSON이 아닐 수 있어(공백, 평문 등) 안전하게 파싱한다.
    실패해도 예외를 던지지 않고 {}를 반환 — 트리거 자체는 raise_for_status()를
    통과했으므로 이미 성공했다고 봐야 하고, 이후 로직은 deploy_id 없이 처리된다."""
    if not resp.content:
        return {}
    try:
        return resp.json()
    except json.JSONDecodeError:
        logger.warning(f"Render 응답이 JSON이 아님 (status={resp.status_code}): {resp.text[:200]!r}")
        return {}


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
