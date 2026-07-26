# 배포 및 환경 설정

---

## 1. 배포 환경

현재 **Render** 플랫폼을 사용합니다.

| 항목 | 값 |
|------|-----|
| 플랫폼 | Render (Web Service) |
| DB | Render PostgreSQL (또는 Neon) |
| 실행 명령 | `uvicorn app.main:app` |
| 사전 배포 명령 | `alembic upgrade head` |
| 기존 운영 도메인 | `https://deep-me-v1.onrender.com` |

---

## 2. 전체 환경변수 목록

### 2.1 LLM 설정

```env
LLM_PROVIDER=openai              # openai | anthropic
LLM_MODEL=gpt-4o-mini            # 기본 모델
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=800
LLM_TIMEOUT_SEC=60
LLM_BACKUP_MODELS=gpt-4o-mini,gpt-4o

OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=                 # 커스텀 엔드포인트 (선택)
OPENAI_ORG_ID=                   # 선택
OPENAI_PROJECT=                  # 선택

ANTHROPIC_API_KEY=               # Anthropic 전환 시 필수
NEED_CARD_MODEL=gpt-4.1-mini     # 욕구분석 모델 개별 지정 (선택)
```

### 2.2 데이터베이스

```env
# 방법 1: 전체 URL
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname

# 방법 2: 개별 항목 (DATABASE_URL 없을 때 조합)
POSTGRES_HOST=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
```

> Render/Neon 호스트는 자동으로 `?sslmode=require`가 추가됩니다.

### 2.3 Google OAuth

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback   # 운영에서는 실제 도메인으로 교체
```

### 2.4 JWT / 인증

```env
JWT_SECRET_KEY=                               # ⚠️ 필수! 미설정 시 서버 시작 실패 (보안 C-2)
JWT_REFRESH_SECRET=                           # ⚠️ 필수! 강력한 랜덤 키 설정
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
REFRESH_TOKEN_EXPIRE_DAYS=21
REFRESH_COOKIE_NAME=__Host-deepme_rtok
SECURE_COOKIE=true                            # tokens.py의 리프레시 쿠키 secure 플래그. HTTPS에서 true, HTTP 로컬에서 false
COOKIE_SECURE=true                            # auth.py의 로그인 응답 쿠키 secure 플래그 — SECURE_COOKIE와 별개 변수! 둘 다 맞춰서 설정할 것
AUTH_SET_COOKIE_ON_POST=false                 # true면 POST /auth/google도 콜백처럼 리프레시 쿠키를 Set-Cookie함 (기본은 모바일 클라이언트 고려해 false)
```

> ⚠️ `SECURE_COOKIE`(`app/backend/core/tokens.py`)와 `COOKIE_SECURE`
> (`app/backend/routers/auth.py`)는 이름이 비슷하지만 서로 다른 환경변수다.
> 운영에서는 둘 다 `true`로 맞춰야 한다.

### 2.5 WebSocket / 대화 정책

```env
POLICY_MAX_TURNS=20              # 대화 최대 턴 수 (레거시 이름 SESSION_MAX_TURNS도 폴백으로 읽힘)
MIN_CLOSE_ORDER=16               # 이 스텝 순서 이전엔 [[CONFIRM_CLOSE]] 토큰이 와도 자동 종료하지 않음
WS_IDLE_TIMEOUT=120              # 유휴 타임아웃 (초)
WS_SEND_BUFFER=20                # 전송 버퍼 크기
WS_HEARTBEAT_SEC=15              # 하트비트 주기 (초)
LLM_STREAM_TIMEOUT=75            # LLM 스트리밍 타임아웃 (초)
RECOMMEND_TIMEOUT=15             # 태스크 추천 타임아웃 (초)
ANALYSIS_CARD_TIMEOUT=45         # 분석카드 생성 타임아웃 (초)
WS_HISTORY_TURNS=8               # LLM 컨텍스트 윈도우 (대화 턴 수)
WS_MAX_USER_TEXT_LEN=8192        # 최대 입력 크기 (bytes)
ACTIVITY_STEP_TYPE=activity_suggest    # 액티비티 제안 스텝의 step_type 값
CANCEL_CLOSE_STEP_TYPE=cancel_close    # 종료 취소 스텝의 step_type 값

# 시스템 프롬프트 유출 방지 (system_prompt.txt 문구가 응답에 그대로 새는 것 감지/마스킹)
LEAK_GUARD_MODE=mask             # mask | off 등
LEAK_GUARD_NGRAM=20
LEAK_GUARD_MIN_MATCH=3

# 인증 없이 /emotion REST를 웹 테스트용 익명 유저로 쓰도록 허용 (운영에서는 false 유지)
EMOTION_NO_AUTH_WEB_TEST=false
WEB_TEST_USER_EMAIL=webtest@local
WEB_TEST_USER_NAME=Web Test User
```

### 2.6 CORS

```env
CORS_ALLOW_ORIGINS=https://deep-me-v1.onrender.com,http://localhost:3000,http://localhost:5173
```

운영 도메인이 변경되면 이 값을 업데이트해야 합니다.

### 2.7 레이트 리밋

```env
RATELIMIT_ENABLED=true    # false면 slowapi 레이트리밋 전체 비활성화. tests/conftest.py는 테스트에서 자동으로 false 처리
```

### 2.8 에러 알림 / 배포 웹훅

```env
DISCORD_ERROR_WEBHOOK_URL=   # 설정 시 ERROR 이상 로그를 이 Discord 채널로 전송 (app/backend/core/logging_config.py)
DISCORD_WEBHOOK_URL=         # GitHub → Render 배포 알림용 별도 채널 (app/backend/routers/deploy_webhook.py)

GITHUB_WEBHOOK_SECRET=       # /webhook/github 서명(HMAC) 검증용
RENDER_DEPLOY_HOOK_URL=      # Render Deploy Hook URL
RENDER_API_KEY=              # Render API 키 (배포 상태 폴링용)
RENDER_SERVICE_ID=           # Render 서비스 ID
```

`DISCORD_ERROR_WEBHOOK_URL` 미설정 시 알림 없이 stdout 로깅만 동작. 같은
로거+메시지는 30초 내 중복 전송하지 않음.

---

## 3. 운영 배포 체크리스트

### 필수 보안 설정
- [ ] `JWT_SECRET_KEY` 필수 설정 (미설정 시 서버 시작 실패 / 보안 C-2)
- [ ] `JWT_REFRESH_SECRET` 필수 설정
- [ ] 프롬프트 수정 API는 운영 환경에서 비활성화됨 (보안 C-1)
- [ ] 테스트 계정/토큰 엔드포인트는 제거됨 (보안 C-3)
- [ ] analyze/desire 라우터 모든 엔드포인트 인증 확인 (보안 C-4)
- [ ] 최신 보안 이슈 현황은 [docs/SECURITY_AUDIT.md](../SECURITY_AUDIT.md) 확인 (P0/P1 미해결 항목 존재 가능)

### 기본 운영 설정
- [ ] `SECURE_COOKIE=true` **및** `COOKIE_SECURE=true` 둘 다 확인 (서로 다른 변수, HTTPS 필수)
- [ ] `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_REDIRECT_URI` 운영 값 설정 확인
- [ ] `DATABASE_URL` 운영 DB 연결 문자열 설정
- [ ] `OPENAI_API_KEY` (또는 `ANTHROPIC_API_KEY`) 유효한 키 설정
- [ ] `CORS_ALLOW_ORIGINS` 운영 도메인 포함 확인
- [ ] Render Pre-deploy Command: `alembic upgrade head` 설정 확인
- [ ] 기존 DB의 경우 `alembic stamp` 상태 확인 후 적용

---

## 4. 로컬 환경 vs 운영 환경 차이

| 항목 | 로컬 | 운영 |
|------|------|------|
| `SECURE_COOKIE` / `COOKIE_SECURE` | false | true |
| `DATABASE_URL` | localhost PostgreSQL | Render/Neon |
| `CORS_ALLOW_ORIGINS` | localhost 포함 | 운영 도메인만 |
| `JWT_SECRET_KEY` | 개발용 (약한 키) | 강력한 랜덤 키 |
| HTTPS | 없음 | 필수 |

---

## 5. LLM 프로바이더 전환

### OpenAI → Anthropic 전환

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-3-5-sonnet-20241022   # Anthropic 모델명
```

### 모델만 변경

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o                       # gpt-4o-mini → gpt-4o
```

재배포 없이 환경변수만 변경하면 즉시 적용됩니다.

---

## 6. Render 배포 설정

저장소 루트의 `render.yaml`에 정의되어 있음. 기존에 대시보드로 수동 생성된 서비스는
render.yaml을 추가해도 자동으로 반영되지 않으므로, Render 대시보드 → 서비스 →
Settings에서 Pre-Deploy Command가 `alembic upgrade head`로 설정되어 있는지
직접 확인해야 함(Blueprint로 재연결하면 render.yaml이 그대로 적용됨).

```yaml
services:
  - type: web
    name: deep-me-v2
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    preDeployCommand: alembic upgrade head
    healthCheckPath: /health/db
```

---

## 7. 헬스체크 URL

Render 서비스 헬스체크에 등록:

```
GET /health
```

DB 연결까지 확인하려면:
```
GET /health/db
```
