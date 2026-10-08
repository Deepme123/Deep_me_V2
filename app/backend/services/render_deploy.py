"""Render 배포 상태 폴링."""

import asyncio
import time
from typing import Any

import httpx

from app.backend.services.deploy_notify_utils import _handle_http_error, _safe_json

RENDER_API_BASE = "https://api.render.com/v1"
DEPLOY_POLL_INTERVAL = 10   # 초
DEPLOY_POLL_TIMEOUT = 600   # 최대 10분


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
