# Run Rules

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
  - `docker compose up -d postgres` 후 서버 기동
- Prod
  - 필수는 외부 DB `DATABASE_URL` 한 개
  - 권장: `DB_SSLMODE=require`, `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET`, `COOKIE_SECURE=true`
  - Google OAuth 미설정이어도 앱은 기동되며, `/auth/google*`만 비활성 동작

## Run Commands
```bash
uvicorn app.main:app --reload
```

```bash
python -m app.main
```
