# Run Rules

## Migration-First Startup Rule
- 서버 기동 전에 반드시 마이그레이션을 먼저 적용합니다.
- 순서를 지키지 않으면 "서버는 뜨지만 런타임에서 테이블/컬럼 오류"가 발생할 수 있습니다.
- 고정 순서:
  1. `alembic upgrade head`
  2. 서버 기동 (`uvicorn app.main:app --reload` 또는 `python -m app.main`)
- 애플리케이션 런타임(`app/backend/main.py`)은 마이그레이션을 수행하지 않고 DB 헬스체크(`/health/db`)만 담당합니다.

## Environment Selection (local vs prod)
- `local`을 선택하는 경우:
  - 로컬에서 `docker-compose.yml`의 Postgres(`deepme/deepme_pw/deepme_db`)를 사용해 개발할 때
  - 템플릿: `.env.local.example`
- `prod`를 선택하는 경우:
  - 배포 환경의 외부 Postgres를 사용할 때
  - 템플릿: `.env.prod.example`

## Apply Template
PowerShell:
```powershell
Copy-Item .env.local.example .env
# or
Copy-Item .env.prod.example .env
```

Bash:
```bash
cp .env.local.example .env
# or
cp .env.prod.example .env
```

## Validation Checklist
- Local
  - `.env`의 `DATABASE_URL`이 다음 값과 일치해야 함:
  - `postgresql+psycopg2://deepme:deepme_pw@localhost:5432/deepme_db`
  - `docker compose up -d postgres`
  - `alembic upgrade head`
  - 이후 서버 기동
- Prod
  - 필수는 외부 DB `DATABASE_URL` 한 개
  - 권장: `DB_SSLMODE=require`, `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET`, `COOKIE_SECURE=true`
  - Google OAuth 미설정이어도 앱은 기동되며, `/auth/google*`만 비활성 동작
  - 배포 파이프라인에서 앱 시작 전에 `alembic upgrade head`를 반드시 선행하고, 실패 시 즉시 배포 중단

## Run Commands
```bash
# 선행 필수
alembic upgrade head

uvicorn app.main:app --reload
```

```bash
# 선행 필수
alembic upgrade head

python -m app.main
```
