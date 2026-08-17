"""배포/PR 결과 Discord 알림."""

import json
import logging
from typing import Any, Optional

import httpx

from app.backend.services.deploy_notify_utils import _handle_http_error, _now_utc, _short_sha

logger = logging.getLogger(__name__)


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
