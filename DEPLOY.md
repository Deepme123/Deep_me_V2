# Deployment Guide

## Objective
- 런타임 장애를 줄이기 위해 "마이그레이션 선행, 서버 후기동" 규칙을 강제합니다.
- 앱 런타임은 스키마 변경을 수행하지 않고, DB 연결 헬스체크만 수행합니다.

## Required Deployment Order
1. 환경 변수 주입 (`DATABASE_URL`, `DB_SSLMODE`, `JWT_*`, `COOKIE_SECURE` 등)
2. 마이그레이션 적용: `alembic upgrade head`
3. 애플리케이션 기동: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. 기동 후 헬스 확인: `GET /health`, `GET /health/db`

## Pipeline Rule (Fail Fast)
- `alembic upgrade head`를 배포 파이프라인의 독립 단계로 둡니다.
- 이 단계가 실패하면 앱 기동 단계를 실행하지 않습니다.
- 즉, 마이그레이션 미적용/실패 상태는 런타임이 아니라 파이프라인 단계에서 먼저 차단합니다.

## Example (Bash)
```bash
set -euo pipefail

alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Example (PowerShell)
```powershell
$ErrorActionPreference = "Stop"

alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
