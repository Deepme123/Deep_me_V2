"""main으로 merge된 PR의 커밋 기록 조회 및 텍스트 생성."""

from typing import Any, Optional

import httpx

from app.backend.services.deploy_notify_utils import _now_utc, _short_sha
from app.backend.services.deploy_security import _is_github_api_url


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
