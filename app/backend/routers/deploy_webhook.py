"""
app/backend/routers/deploy_webhook.py

GitHub main 브랜치 커밋 감지 → Render 자동 배포 → Discord 알림 라우터.
PR merge 감지 → 커밋 기록 txt 파일 → Discord 파일 첨부 알림.
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
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 환경변수
# ──────────────────────────────────────────────
GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")

# GitHub는 브랜치 필터링 없이 모든 push 이벤트를 이 엔드포인트로 보내므로,
# main → 운영 / develop → 테스트로 라우팅하는 건 코드에서 처리한다.
BRANCH_ENV_MAP = {"main": "prod", "develop": "test"}

ENV_CONFIGS: dict[str, dict[str, str]] = {
    "prod": {
        "label": "운영",
        "deploy_hook": os.getenv("RENDER_DEPLOY_HOOK_URL_PROD", ""),
        "api_key": os.getenv("RENDER_API_KEY_PROD", ""),
        "service_id": os.getenv("RENDER_SERVICE_ID_PROD", ""),
        "discord": os.getenv("DISCORD_WEBHOOK_URL_PROD", ""),
    },
    "test": {
        "label": "테스트",
        "deploy_hook": os.getenv("RENDER_DEPLOY_HOOK_URL_TEST", ""),
        "api_key": os.getenv("RENDER_API_KEY_TEST", ""),
        "service_id": os.getenv("RENDER_SERVICE_ID_TEST", ""),
        "discord": os.getenv("DISCORD_WEBHOOK_URL_TEST", ""),
    },
}

RENDER_API_BASE = "https://api.render.com/v1"
DEPLOY_POLL_INTERVAL = 10   # 초
DEPLOY_POLL_TIMEOUT = 600   # 최대 10분
GITHUB_API_HOST = "api.github.com"

router = APIRouter(tags=["deploy"])


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────
def _verify_signature(payload_bytes: bytes, signature: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _signature_required_and_valid(raw_body: bytes, signature: str) -> bool:
    """GITHUB_WEBHOOK_SECRET이 설정된 경우, 서명이 없거나 틀리면 거부.

    이전엔 `signature` 헤더 자체가 없으면 검증을 통째로 스킵해서
    헤더를 안 보내는 것만으로 인증을 우회할 수 있었음.
    """
    if not GITHUB_WEBHOOK_SECRET:
        return True
    if not signature:
        return False
    return _verify_signature(raw_body, signature, GITHUB_WEBHOOK_SECRET)


def _is_github_api_url(url: str) -> bool:
    """commits_url은 PR 웹훅 페이로드에서 그대로 들어오는 값이라,
    GitHub API 호스트가 아니면 거부해서 SSRF를 막음."""
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == GITHUB_API_HOST


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


# ──────────────────────────────────────────────
# Render 상태 폴링
# ──────────────────────────────────────────────
async def _poll_render_deploy(deploy_id: str, api_key: str, service_id: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{RENDER_API_BASE}/services/{service_id}/deploys/{deploy_id}"
    deadline = time.time() + DEPLOY_POLL_TIMEOUT

    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() < deadline:
            await asyncio.sleep(DEPLOY_POLL_INTERVAL)
            try:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                status = _safe_json(resp).get("status", "")

                if status == "live":
                    svc_resp = await client.get(
                        f"{RENDER_API_BASE}/services/{service_id}",
                        headers=headers
                    )
                    svc_data = _safe_json(svc_resp) if svc_resp.status_code == 200 else {}
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
    env_label: str,
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
            "title": f"✅ [{env_label}] 배포 성공",
            "description": f"`{short}` 커밋이 {env_label} 서버에 성공적으로 배포됐어.",
            "color": 0x57F287,
            "fields": fields,
            "footer": {"text": "Deep Me Deploy Bot"},
        }]}
    else:
        return {"embeds": [{
            "title": f"❌ [{env_label}] 배포 실패",
            "description": f"`{short}` 커밋 {env_label} 서버 배포 중 오류 발생.",
            "color": 0xED4245,
            "fields": [
                {"name": "커밋", "value": f"`{short}` — {commit_message[:100]}", "inline": False},
                {"name": "작성자", "value": author, "inline": True},
                {"name": "시각", "value": now, "inline": True},
                {"name": "오류", "value": error_detail[:500] or "알 수 없는 오류", "inline": False},
            ],
            "footer": {"text": "Deep Me Deploy Bot"},
        }]}


async def _send_discord(embed_payload: dict[str, Any], webhook_url: str) -> None:
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL 미설정 — 알림 건너뜀")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                webhook_url,
                json=embed_payload,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            logger.info("Discord 알림 전송 완료")
    except Exception as e:
        logger.error(f"Discord 알림 실패: {_handle_http_error(e)}")


async def _send_discord_file(
    embed_payload: dict[str, Any],
    filename: str,
    file_content: str,
    webhook_url: str,
) -> None:
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL 미설정 — 알림 건너뜀")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                webhook_url,
                data={"payload_json": json.dumps(embed_payload)},
                files={"file": (filename, file_content.encode("utf-8"), "text/plain")},
            )
            resp.raise_for_status()
            logger.info(f"Discord 파일 첨부 알림 전송 완료: {filename}")
    except Exception as e:
        logger.error(f"Discord 파일 첨부 알림 실패: {_handle_http_error(e)}")


# ──────────────────────────────────────────────
# PR 커밋 기록
# ──────────────────────────────────────────────
async def _fetch_pr_commits(commits_url: str) -> list[dict[str, Any]]:
    if not _is_github_api_url(commits_url):
        raise ValueError(f"commits_url이 GitHub API 호스트가 아님: {commits_url}")

    commits: list[dict[str, Any]] = []
    url: Optional[str] = commits_url + "?per_page=100"
    headers = {"Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=30) as client:
        while url:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            commits.extend(resp.json())
            url = None
            for part in resp.headers.get("Link", "").split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
                    if _is_github_api_url(next_url):
                        url = next_url
    return commits


def _build_commit_history_txt(
    pr_number: int,
    pr_title: str,
    head_branch: str,
    base_branch: str,
    merged_by: str,
    commits: list[dict[str, Any]],
) -> str:
    lines = [
        f"PR #{pr_number}: {head_branch} → {base_branch}",
        f"제목: {pr_title}",
        f"Merged by: {merged_by} | {_now_utc()}",
        f"총 커밋 수: {len(commits)}",
        "─" * 50,
    ]
    for i, c in enumerate(commits, 1):
        sha = _short_sha(c.get("sha", ""))
        msg = (c.get("commit", {}).get("message", "") or "").split("\n")[0]
        author = (
            (c.get("author") or {}).get("login")
            or c.get("commit", {}).get("author", {}).get("name", "unknown")
        )
        date_raw = c.get("commit", {}).get("author", {}).get("date", "")
        date = date_raw[:10] if date_raw else "unknown"
        lines.append(f"[{i}] {sha} — {msg[:80]} ({author}, {date})")
    return "\n".join(lines)


async def _run_pr_pipeline(payload: dict[str, Any], signature: str, raw_body: bytes) -> None:
    # 1. 서명 검증
    if not _signature_required_and_valid(raw_body, signature):
        logger.warning("GitHub 웹훅 서명 검증 실패 — 무시")
        return

    # 2. main으로 merge된 PR인지 확인
    action = payload.get("action", "")
    pr = payload.get("pull_request", {})
    if action != "closed" or not pr.get("merged"):
        logger.info(f"PR 이벤트 action={action}, merged={pr.get('merged')} — 건너뜀")
        return

    base_branch = pr.get("base", {}).get("ref", "")
    if base_branch != "main":
        logger.info(f"PR base='{base_branch}' — main 아님, 건너뜀")
        return

    pr_number: int = pr.get("number", 0)
    pr_title: str = pr.get("title", "")
    head_branch: str = pr.get("head", {}).get("ref", "")
    merged_by: str = (pr.get("merged_by") or {}).get("login", "unknown")
    commits_url: str = pr.get("commits_url", "")
    logger.info(f"PR #{pr_number} merged into main: {head_branch} by {merged_by}")

    # PR merge 알림은 base가 항상 main(운영)이므로 운영 채널로 고정 전송
    discord_url = ENV_CONFIGS["prod"]["discord"]

    # 3. 커밋 목록 조회
    try:
        commits = await _fetch_pr_commits(commits_url)
    except Exception as e:
        error_msg = _handle_http_error(e)
        logger.error(f"PR 커밋 목록 조회 실패: {error_msg}")
        await _send_discord({"embeds": [{
            "title": f"⚠️ PR #{pr_number} 커밋 기록 조회 실패",
            "description": error_msg,
            "color": 0xED4245,
            "footer": {"text": "Deep Me Deploy Bot"},
        }]}, discord_url)
        return

    # 4. txt 생성 + Discord 파일 첨부 전송
    txt_content = _build_commit_history_txt(
        pr_number, pr_title, head_branch, base_branch, merged_by, commits
    )
    embed = {"embeds": [{
        "title": f"📋 PR #{pr_number} 커밋 기록",
        "description": f"`{head_branch}` → `{base_branch}`",
        "color": 0x5865F2,
        "fields": [
            {"name": "제목", "value": pr_title[:100], "inline": False},
            {"name": "Merged by", "value": merged_by, "inline": True},
            {"name": "커밋 수", "value": str(len(commits)), "inline": True},
            {"name": "시각", "value": _now_utc(), "inline": True},
        ],
        "footer": {"text": "Deep Me Deploy Bot"},
    }]}
    await _send_discord_file(embed, f"pr_{pr_number}_commits.txt", txt_content, discord_url)


# ──────────────────────────────────────────────
# 파이프라인 (백그라운드 실행)
# ──────────────────────────────────────────────
async def _run_pipeline(payload: dict[str, Any], signature: str, raw_body: bytes) -> None:
    # 1. 서명 검증
    if not _signature_required_and_valid(raw_body, signature):
        logger.warning("GitHub 웹훅 서명 검증 실패 — 무시")
        return

    # 2. main(운영)/develop(테스트) push인지 확인
    ref = payload.get("ref", "")
    branch = ref.replace("refs/heads/", "")
    env_name = BRANCH_ENV_MAP.get(branch)
    if env_name is None:
        logger.info(f"'{branch}' 브랜치 push — 파이프라인 건너뜀")
        return
    cfg = ENV_CONFIGS[env_name]
    env_label = cfg["label"]

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
    logger.info(f"'{branch}' 브랜치({env_label}) push 감지: {_short_sha(commit_sha)} by {author}")

    # 4. Render 배포 트리거
    # Deploy Hook URL이 있으면 그걸 우선 쓰고(기존 방식), 없으면
    # API 키 + 서비스ID로 POST /services/{id}/deploys를 직접 호출한다.
    # Deploy Hook은 Render 대시보드에서만 발급 가능해서, API 키만으로도
    # 같은 결과(수동 발급 없이 배포 트리거)를 낼 수 있게 하기 위함.
    if not cfg["deploy_hook"] and not (cfg["api_key"] and cfg["service_id"]):
        logger.error(f"RENDER_DEPLOY_HOOK_URL_{env_name.upper()} 및 API 키/서비스ID 모두 미설정")
        await _send_discord(_build_discord_embed(
            False, commit_sha, commit_message, author,
            f"RENDER_DEPLOY_HOOK_URL_{env_name.upper()} 또는 "
            f"RENDER_API_KEY_{env_name.upper()}/RENDER_SERVICE_ID_{env_name.upper()} 환경변수가 없어.",
            None, env_label
        ), cfg["discord"])
        return

    deploy_id = ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if cfg["deploy_hook"]:
                resp = await client.post(cfg["deploy_hook"])
                resp.raise_for_status()
                data = _safe_json(resp)
                deploy_id = data.get("deploy", {}).get("id", "") if isinstance(data, dict) else ""
            else:
                resp = await client.post(
                    f"{RENDER_API_BASE}/services/{cfg['service_id']}/deploys",
                    headers={"Authorization": f"Bearer {cfg['api_key']}"},
                )
                resp.raise_for_status()
                data = _safe_json(resp)
                deploy_id = data.get("id", "") if isinstance(data, dict) else ""
            logger.info(f"Render 배포 트리거 완료 — deploy_id: {deploy_id}")
    except Exception as e:
        error_msg = _handle_http_error(e)
        logger.error(f"Render 배포 트리거 실패: {error_msg}")
        await _send_discord(_build_discord_embed(
            False, commit_sha, commit_message, author, error_msg, None, env_label
        ), cfg["discord"])
        return

    # 5. 배포 상태 폴링 (API 키 있을 때만)
    if deploy_id and cfg["api_key"] and cfg["service_id"]:
        poll = await _poll_render_deploy(deploy_id, cfg["api_key"], cfg["service_id"])
        success = poll["status"] == "live"
        await _send_discord(_build_discord_embed(
            success, commit_sha, commit_message, author,
            poll.get("error", ""), poll.get("deploy_url") if success else None, env_label
        ), cfg["discord"])
    else:
        # 트리거만 하고 성공으로 처리
        logger.info(f"RENDER_API_KEY_{env_name.upper()} 미설정 — 트리거 완료로 처리")
        await _send_discord(_build_discord_embed(
            True, commit_sha, commit_message, author,
            "배포 트리거 완료. 상태는 Render 대시보드에서 확인해.", None, env_label
        ), cfg["discord"])


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
    if event_type not in ("push", "pull_request"):
        return {"message": f"'{event_type}' 이벤트는 처리 안 해 (push, pull_request만 처리함)"}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON 파싱 실패")

    if event_type == "push":
        asyncio.create_task(_run_pipeline(payload, signature, body))
        return {"message": "웹훅 수신 완료 — 배포 파이프라인 실행 중"}

    asyncio.create_task(_run_pr_pipeline(payload, signature, body))
    return {"message": "웹훅 수신 완료 — PR 커밋 기록 처리 중"}