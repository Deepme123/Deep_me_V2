"""
app/backend/routers/deploy_webhook.py

GitHub main 브랜치 커밋 감지 → Render 자동 배포 → Discord 알림 라우터.
PR merge 감지 → 커밋 기록 txt 파일 → Discord 파일 첨부 알림.
app/main.py에 include_router로 등록해서 사용.
"""

import asyncio
import json
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.backend.services.deploy_discord import _build_discord_embed, _send_discord, _send_discord_file
from app.backend.services.deploy_notify_utils import _handle_http_error, _now_utc, _safe_json, _short_sha
from app.backend.services.deploy_pr_history import _build_commit_history_txt, _fetch_pr_commits
from app.backend.services.deploy_security import _signature_required_and_valid
from app.backend.services.render_deploy import RENDER_API_BASE, _poll_render_deploy

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 환경변수
# ──────────────────────────────────────────────
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

router = APIRouter(tags=["deploy"])


async def _run_pr_pipeline(payload: dict, signature: str, raw_body: bytes) -> None:
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
async def _run_pipeline(payload: dict, signature: str, raw_body: bytes) -> None:
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
