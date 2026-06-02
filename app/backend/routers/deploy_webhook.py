"""
app/backend/routers/deploy_webhook.py

GitHub main 브랜치 커밋 감지 → Render 자동 배포 → Discord 알림 라우터.
app/main.py에 include_router로 등록해서 사용.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 환경변수
# ──────────────────────────────────────────────
GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")
RENDER_DEPLOY_HOOK_URL: str = os.getenv("RENDER_DEPLOY_HOOK_URL", "")
RENDER_API_KEY: str = os.getenv("RENDER_API_KEY", "")
RENDER_SERVICE_ID: str = os.getenv("RENDER_SERVICE_ID", "")
DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

RENDER_API_BASE = "https://api.render.com/v1"
DEPLOY_POLL_INTERVAL = 10   # 초
DEPLOY_POLL_TIMEOUT = 600   # 최대 10분

router = APIRouter(tags=["deploy"])


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────
def _verify_signature(payload_bytes: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _short_sha(sha: str) -> str:
    return sha[:7] if sha else "unknown"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


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


# ──────────────────────────────────────────────
# Render 상태 폴링
# ──────────────────────────────────────────────
async def _poll_render_deploy(deploy_id: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}"}
    url = f"{RENDER_API_BASE}/services/{RENDER_SERVICE_ID}/deploys/{deploy_id}"
    deadline = time.time() + DEPLOY_POLL_TIMEOUT

    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() < deadline:
            await asyncio.sleep(DEPLOY_POLL_INTERVAL)
            try:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                status = resp.json().get("status", "")

                if status == "live":
                    svc_resp = await client.get(
                        f"{RENDER_API_BASE}/services/{RENDER_SERVICE_ID}",
                        headers=headers
                    )
                    svc_data = svc_resp.json() if svc_resp.status_code == 200 else {}
                    deploy_url = svc_data.get("serviceDetails", {}).get("url", "")
                    return {"status": "live", "deploy_url": deploy_url, "error": ""}

                if status in ("build_failed", "update_failed", "canceled", "deactivated"):
                    return {"status": "failed", "deploy_url": "", "error": f"Render 상태: {status}"}

            except Exception as e:
                return {"status": "failed", "deploy_url": "", "error": _handle_http_error(e)}

    return {"status": "failed", "deploy_url": "", "error": "배포 타임아웃 (10분 초과)"}


# ──────────────────────────────────────────────
# Discord 알림
# ──────────────────────────────────────────────
def _build_discord_embed(
    success: bool,
    commit_sha: str,
    commit_message: str,
    author: str,
    error_detail: str,
    deploy_url: Optional[str],
) -> dict[str, Any]:
    short = _short_sha(commit_sha)
    now = _now_utc()

    if success:
        fields = [
            {"name": "커밋", "value": f"`{short}` — {commit_message[:100]}", "inline": False},
            {"name": "작성자", "value": author, "inline": True},
            {"name": "시각", "value": now, "inline": True},
        ]
        if deploy_url:
            fields.append({"name": "🔗 배포 URL", "value": deploy_url, "inline": False})
        return {"embeds": [{
            "title": "✅ 배포 성공",
            "description": f"`{short}` 커밋이 성공적으로 배포됐어.",
            "color": 0x57F287,
            "fields": fields,
            "footer": {"text": "Deep Me Deploy Bot"},
        }]}
    else:
        return {"embeds": [{
            "title": "❌ 배포 실패",
            "description": f"`{short}` 커밋 배포 중 오류 발생.",
            "color": 0xED4245,
            "fields": [
                {"name": "커밋", "value": f"`{short}` — {commit_message[:100]}", "inline": False},
                {"name": "작성자", "value": author, "inline": True},
                {"name": "시각", "value": now, "inline": True},
                {"name": "오류", "value": error_detail[:500] or "알 수 없는 오류", "inline": False},
            ],
            "footer": {"text": "Deep Me Deploy Bot"},
        }]}


async def _send_discord(embed_payload: dict[str, Any]) -> None:
    if not DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL 미설정 — 알림 건너뜀")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                DISCORD_WEBHOOK_URL,
                json=embed_payload,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            logger.info("Discord 알림 전송 완료")
    except Exception as e:
        logger.error(f"Discord 알림 실패: {_handle_http_error(e)}")


# ──────────────────────────────────────────────
# 파이프라인 (백그라운드 실행)
# ──────────────────────────────────────────────
async def _run_pipeline(payload: dict[str, Any], signature: str) -> None:
    # 1. 서명 검증
    if signature and GITHUB_WEBHOOK_SECRET:
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
        if not _verify_signature(payload_bytes, signature, GITHUB_WEBHOOK_SECRET):
            logger.warning("GitHub 웹훅 서명 검증 실패 — 무시")
            return

    # 2. main 브랜치 push인지 확인
    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "")
    if branch != "main":
        logger.info(f"'{branch}' 브랜치 push — 파이프라인 건너뜀")
        return

    # 3. 커밋 정보 추출
    head_commit = payload.get("head_commit") or {}
    commits = payload.get("commits", [])
    commit = head_commit or (commits[-1] if commits else {})
    if not commit:
        logger.warning("커밋 정보 없음 — 파이프라인 중단")
        return

    commit_sha = commit.get("id", "")
    commit_message = (commit.get("message", "") or "").split("\n")[0]
    author = (
        commit.get("author", {}).get("username")
        or commit.get("author", {}).get("name", "unknown")
    )
    logger.info(f"main 브랜치 push 감지: {_short_sha(commit_sha)} by {author}")

    # 4. Render 배포 트리거
    if not RENDER_DEPLOY_HOOK_URL:
        logger.error("RENDER_DEPLOY_HOOK_URL 미설정")
        await _send_discord(_build_discord_embed(
            False, commit_sha, commit_message, author,
            "RENDER_DEPLOY_HOOK_URL 환경변수가 없어.", None
        ))
        return

    deploy_id = ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(RENDER_DEPLOY_HOOK_URL)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            deploy_id = data.get("id", "") if isinstance(data, dict) else ""
            logger.info(f"Render 배포 트리거 완료 — deploy_id: {deploy_id}")
    except Exception as e:
        error_msg = _handle_http_error(e)
        logger.error(f"Render 배포 트리거 실패: {error_msg}")
        await _send_discord(_build_discord_embed(
            False, commit_sha, commit_message, author, error_msg, None
        ))
        return

    # 5. 배포 상태 폴링 (API 키 있을 때만)
    if deploy_id and RENDER_API_KEY and RENDER_SERVICE_ID:
        poll = await _poll_render_deploy(deploy_id)
        success = poll["status"] == "live"
        await _send_discord(_build_discord_embed(
            success, commit_sha, commit_message, author,
            poll.get("error", ""), poll.get("deploy_url") if success else None
        ))
    else:
        # 트리거만 하고 성공으로 처리
        logger.info("RENDER_API_KEY 미설정 — 트리거 완료로 처리")
        await _send_discord(_build_discord_embed(
            True, commit_sha, commit_message, author,
            "배포 트리거 완료. 상태는 Render 대시보드에서 확인해.", None
        ))


# ──────────────────────────────────────────────
# 라우터 엔드포인트
# ──────────────────────────────────────────────
@router.post("/webhook/github")
async def github_webhook(request: Request):
    """GitHub push 웹훅 수신 → 배포 파이프라인 백그라운드 실행."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    event_type = request.headers.get("X-GitHub-Event", "")

    if event_type == "ping":
        return {"message": "pong — 웹훅 연결 확인 완료"}
    if event_type and event_type != "push":
        return {"message": f"'{event_type}' 이벤트는 처리 안 해 (push만 처리함)"}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON 파싱 실패")

    # 즉시 200 반환 후 백그라운드에서 파이프라인 실행
    asyncio.create_task(_run_pipeline(payload, signature))
    return {"message": "웹훅 수신 완료 — 파이프라인 실행 중"}