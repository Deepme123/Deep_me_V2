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

### 2.3 JWT / 인증

```env
JWT_SECRET_KEY=                               # ⚠️ 필수! 미설정 시 서버 시작 실패 (보안 C-2)
JWT_REFRESH_SECRET=                           # ⚠️ 필수! 강력한 랜덤 키 설정
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
REFRESH_TOKEN_EXPIRE_DAYS=21
REFRESH_COOKIE_NAME=__Host-deepme_rtok
SECURE_COOKIE=true                            # HTTPS에서 true, HTTP 로컬에서 false
```

### 2.4 WebSocket / 세션

```env
SESSION_MAX_TURNS=20             # 대화 최대 턴 수
WS_IDLE_TIMEOUT=120              # 유휴 타임아웃 (초)
WS_SEND_BUFFER=20                # 전송 버퍼 크기
WS_HEARTBEAT_SEC=15              # 하트비트 주기 (초)
LLM_STREAM_TIMEOUT=75            # LLM 스트리밍 타임아웃 (초)
RECOMMEND_TIMEOUT=15             # 태스크 추천 타임아웃 (초)
ANALYSIS_CARD_TIMEOUT=45         # 분석카드 생성 타임아웃 (초)
WS_HISTORY_TURNS=8               # LLM 컨텍스트 윈도우 (대화 턴 수)
WS_MAX_USER_TEXT_LEN=8192        # 최대 입력 크기 (bytes)
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

---

## 3. 운영 배포 체크리스트

### 필수 보안 설정
- [ ] `JWT_SECRET_KEY` 필수 설정 (미설정 시 서버 시작 실패 / 보안 C-2)
- [ ] `JWT_REFRESH_SECRET` 필수 설정
- [ ] 프롬프트 수정 API는 운영 환경에서 비활성화됨 (보안 C-1)
- [ ] 테스트 계정/토큰 엔드포인트는 제거됨 (보안 C-3)
- [ ] analyze 서브앱 모든 엔드포인트 인증 확인 (보안 C-4)

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
