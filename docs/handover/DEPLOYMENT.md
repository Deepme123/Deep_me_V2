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
LLM_MODEL=gpt-4o-mini            # 미설정 시 코드 기본값(gpt-5.4-mini-2026-03-17)으로 폴백
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=800
LLM_TIMEOUT_SEC=60
LLM_BACKUP_MODELS=gpt-4o-mini,gpt-4o

OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=                 # 커스텀 엔드포인트 (선택)
OPENAI_ORG_ID=                   # 선택
OPENAI_PROJECT=                  # 선택

ANTHROPIC_API_KEY=               # Anthropic 전환 시 필수
NEED_CARD_MODEL=gpt-4.1-mini     # 욕구분석 모델 개별 지정 (선택, LLM_MODEL의 레거시 오버라이드 이름)
```

`app/core/llm_settings.get_llm_settings()`가 세 서비스(backend/analyze/desire)
공용 로더입니다. `LLM_MODEL`이 비어 있으면 각 서비스가 자체 `model_default`
인자값으로 폴백하는데, 현재 코드 기준 세 서비스 모두 `gpt-5.4-mini-2026-03-17`로
동일합니다. `.env.example`의 `gpt-4o-mini`는 예시값일 뿐, 실제로 값을 넣지
않으면 저 폴백값이 쓰입니다.

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

### 2.3 JWT / 인증

```env
JWT_SECRET_KEY=                               # ⚠️ 필수! 미설정 시 서버 시작 실패 (보안 C-2)
JWT_REFRESH_SECRET=                           # ⚠️ 필수! 강력한 랜덤 키 설정
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120               # Access Token TTL (app/backend/core/tokens.py 기본값)
REFRESH_TOKEN_EXPIRE_DAYS=21
REFRESH_COOKIE_NAME=__Host-deepme_rtok
SECURE_COOKIE=true                            # 리프레시 토큰 쿠키. HTTPS에서 true, HTTP 로컬에서 false

# Google OAuth (인증 흐름 자체에 필수 — 미설정 시 /auth/* 가 503)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback   # GET /auth/callback 리디렉트 대상

# 액세스 토큰을 쿠키로도 내려줄지 (웹 혼용 환경 전용, 기본 비활성)
AUTH_SET_COOKIE_ON_POST=false
COOKIE_SECURE=false                           # AUTH_SET_COOKIE_ON_POST=true일 때만 의미 있음
```

### 2.4 WebSocket / 세션

```env
SESSION_MAX_TURNS=20              # 대화 최대 턴 수. POLICY_MAX_TURNS가 설정되어 있으면 그 값이 우선함
POLICY_MAX_TURNS=                 # SESSION_MAX_TURNS의 상위 우선순위 이름 (미설정 시 SESSION_MAX_TURNS 사용)
WS_IDLE_TIMEOUT=600               # 유휴 타임아웃 (초)
WS_SEND_BUFFER=50                 # 전송 버퍼 크기
WS_HEARTBEAT_SEC=30                # 하트비트 주기 (초)
LLM_STREAM_TIMEOUT=120             # LLM 스트리밍 타임아웃 (초)
RECOMMEND_TIMEOUT=15               # 태스크 추천 타임아웃 (초)
ANALYSIS_CARD_TIMEOUT=75           # 분석카드/욕구카드 생성 타임아웃 (초). LLM_TIMEOUT_SEC(기본 60)보다
                                    # 여유 있게 잡아야 함 — 그보다 작으면 정상 응답도 타임아웃 처리됨
WS_HISTORY_TURNS=8                 # LLM 컨텍스트 윈도우 (대화 턴 수, 5~10 사이로 clamp됨)
WS_MAX_USER_TEXT_LEN=8192          # 최대 입력 크기 (bytes)
MIN_CLOSE_ORDER=16                 # [[CONFIRM_CLOSE]] 마커를 유효하게 인정하는 최소 user_order
GREETING_DELAY_MIN_SEC=1.0         # 연결 직후 서버가 인사 메시지를 보내기 전 최소 대기(초)
GREETING_DELAY_MAX_SEC=2.0         # 위 최대 대기(초)
ACTIVITY_STEP_TYPE=activity_suggest   # 액티비티 제안 마커 스텝의 step_type 값
CANCEL_CLOSE_STEP_TYPE=              # cancel_close 마커 스텝의 step_type 값 (close_policy.py 기본값 사용)
EMOTION_NO_AUTH_WEB_TEST=false     # true면 토큰 없이도 웹 테스트용 익명 유저로 처리 허용
WEB_TEST_USER_EMAIL=webtest@local  # 위 옵션 켰을 때 사용할 익명 유저 이메일
WEB_TEST_USER_NAME=Web Test User
LEAK_GUARD_NGRAM=20                # 시스템 프롬프트 유출 방지 필터의 n-gram 크기
LEAK_GUARD_MIN_MATCH=3
LEAK_GUARD_MODE=mask               # mask | block 등
RATELIMIT_ENABLED=true             # false면 전체 레이트리밋 비활성 (tests/conftest.py가 테스트 시 false로 설정)
```

### 2.5 CORS

```env
CORS_ALLOW_ORIGINS=https://deep-me-v1.onrender.com,http://localhost:3000,http://localhost:5173
```

운영 도메인이 변경되면 이 값을 업데이트해야 합니다.

### 2.6 에러 알림

```env
DISCORD_ERROR_WEBHOOK_URL=   # 설정 시 ERROR 이상 로그를 해당 Discord 채널로 전송
```

미설정 시 알림 없이 stdout 로깅만 동작(기존과 동일). 같은 로거+메시지는
30초 내 중복 전송하지 않음(`app/backend/core/logging_config.py`).

### 2.7 배포 웹훅 (운영/테스트 분리)

`app/backend/routers/deploy_webhook.py`가 GitHub push 웹훅(`POST /webhook/github`)을
받아 `main` 브랜치는 운영(PROD), `develop` 브랜치는 테스트(TEST) Render 서비스로
각각 배포를 트리거하고 Discord로 결과를 알린다. GitHub는 브랜치 필터 없이 모든
push 이벤트를 보내므로 웹훅 자체는 하나만 등록하면 되고, 브랜치별 라우팅은
코드(`BRANCH_ENV_MAP`)에서 처리한다.

```env
GITHUB_WEBHOOK_SECRET=              # /webhook/github 서명(HMAC) 검증용, 운영/테스트 공용

RENDER_DEPLOY_HOOK_URL_PROD=        # 운영(deep-me-v2) Deploy Hook URL
RENDER_API_KEY_PROD=                # 운영 배포 상태 폴링용 API 키
RENDER_SERVICE_ID_PROD=             # 운영 서비스 ID
DISCORD_WEBHOOK_URL_PROD=           # 운영 배포 알림 채널

RENDER_DEPLOY_HOOK_URL_TEST=        # 테스트(deep-me-v2-test) Deploy Hook URL
RENDER_API_KEY_TEST=                # 테스트 배포 상태 폴링용 API 키
RENDER_SERVICE_ID_TEST=             # 테스트 서비스 ID
DISCORD_WEBHOOK_URL_TEST=           # 테스트 배포 알림 채널
```

`RENDER_API_KEY_*`/`RENDER_SERVICE_ID_*` 미설정 시 배포는 트리거만 하고
Render 대시보드에서 상태를 직접 확인하라는 알림으로 대체된다.

---

## 3. 운영 배포 체크리스트

### 필수 보안 설정
- [ ] `JWT_SECRET_KEY` 필수 설정 (미설정 시 서버 시작 실패 / 보안 C-2)
- [ ] `JWT_REFRESH_SECRET` 필수 설정
- [ ] 프롬프트 수정 API는 운영 환경에서 비활성화됨 (보안 C-1)
- [ ] 테스트 계정/토큰 엔드포인트는 제거됨 (보안 C-3)
- [ ] analyze 라우터 모든 엔드포인트 인증 확인 (보안 C-4)

### 기본 운영 설정
- [ ] `SECURE_COOKIE=true` 확인 (HTTPS 필수)
- [ ] `DATABASE_URL` 운영 DB 연결 문자열 설정
- [ ] `OPENAI_API_KEY` (또는 `ANTHROPIC_API_KEY`) 유효한 키 설정
- [ ] `CORS_ALLOW_ORIGINS` 운영 도메인 포함 확인
- [ ] Render Pre-deploy Command: `alembic upgrade head` 설정 확인
- [ ] 기존 DB의 경우 `alembic stamp` 상태 확인 후 적용

---

## 4. 로컬 환경 vs 운영 환경 차이

| 항목 | 로컬 | 운영 |
|------|------|------|
| `SECURE_COOKIE` | false | true |
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

  - type: web
    name: deep-me-v2-test
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
