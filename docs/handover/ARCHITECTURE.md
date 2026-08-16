# 시스템 아키텍처

---

## 1. 전체 구조

Deep_me V2는 **단일 FastAPI 앱** 안에 세 논리적 서비스 패키지(backend/analyze/desire)를
라우터 단위로 얹은 구조입니다. `app/analyze`, `app/desire`는 별도로 마운트된 서브앱이
아니라, `app.main`에서 `include_router(..., prefix="/analyze")` /
`include_router(..., prefix="/desire")`로 라우터만 등록됩니다. 하나의 Uvicorn
프로세스가 하나의 PostgreSQL DB를 바라보며 모든 요청을 처리합니다.

```
┌─────────────────────────────────────────────────────┐
│                   Uvicorn (Port 8000)               │
│                                                     │
│  app/main.py  ← FastAPI 앱 본체 + 라우터 include     │
│  ├── app.backend.main:app  가 실제 FastAPI() 인스턴스 │
│  │     (인증/감정대화/태스크, prefix 없음)             │
│  ├── /analyze  app.analyze.routers.*  (분석카드/요약/만족도) │
│  └── /desire   app.desire.routers.need_card  (욕구분석) │
└─────────────────────────────────────────────────────┘
         │                         │
    REST + WebSocket           PostgreSQL
```

`app/main.py` 전체:

```python
from app.backend.main import app as app

from app.analyze.routers import cards as cards_router
from app.analyze.routers import summaries as summaries_router
from app.analyze.routers import satisfaction as satisfaction_router
from app.desire.routers.need_card import router as need_card_router

app.include_router(cards_router.router, prefix="/analyze")
app.include_router(summaries_router.router, prefix="/analyze")
app.include_router(satisfaction_router.router, prefix="/analyze")
app.include_router(need_card_router, prefix="/desire")
```

과거에 있던 `app/backend/demo_ui/`(서버 렌더링 QA 데모)와 `app/analyze/main.py` /
`app/analyze/db.py`(서브앱 흉내를 내던 파일)는 제거되었습니다.

---

## 2. 서비스별 역할

### 2.1 Backend Service (`app/backend/`)

핵심 서비스. 인증, 사용자, 감정 대화, 태스크를 담당합니다.

```
app/backend/
├── main.py                  # FastAPI 앱 생성, CORS, 레이트리미터, 라우터 등록
├── core/
│   ├── tokens.py            # JWT 생성/검증, 리프레시 토큰 해시/쿠키
│   ├── jwt.py                # decode_access_token 등 디코딩 헬퍼
│   ├── prompt_loader.py      # 시스템/태스크 프롬프트 로드 (resources/*.txt)
│   ├── greeting_loader.py    # 인사 문구 목록 로드 (resources/greeting_messages.txt)
│   ├── logging_config.py     # 로깅 설정, Discord 에러 웹훅 전송
│   └── rate_limit.py         # slowapi 레이트 리미터
├── dependencies/
│   └── auth.py               # get_current_user 등 인증 의존성
├── models/
│   ├── user.py                # User SQLModel
│   ├── emotion.py             # EmotionSession, EmotionStep SQLModel
│   ├── emotion_step.py        # EmotionStep 재노출 (models.emotion에서 import)
│   ├── greeting_message.py    # GreetingMessageStat (인사 문구 선택 횟수 카운터)
│   ├── task.py                 # Task SQLModel
│   └── refresh_token.py       # RefreshToken SQLModel
├── schemas/
│   ├── emotion.py             # 감정 대화 REST/WS 요청·응답 Pydantic 스키마
│   └── task.py                 # 태스크 스키마
├── routers/
│   ├── auth.py                 # /auth/* (Google OAuth, 토큰 갱신/취소)
│   ├── emotion.py              # /emotion/* (세션, 스텝 REST API)
│   ├── emotion_ws.py           # /ws/emotion (WebSocket 핸들러)
│   ├── task.py                  # /tasks/*
│   ├── health_llm.py           # /health/* (llm 관련)
│   ├── user.py                  # /users/*
│   └── deploy_webhook.py       # /webhook/github (GitHub → Render 배포 + Discord 알림)
├── services/
│   ├── llm_service.py          # LLM 추상화 레이어, stream_noa_response
│   ├── ws_protocol.py          # WebSocket 메시지 파싱/토큰 추출, MSG_* 상수
│   ├── ws_session_service.py   # 세션 생명주기 관리 (생성/스텝 커밋/종료)
│   ├── ws_streaming.py         # 스트리밍 전송 버퍼(백프레셔), OutboundWSChannel
│   ├── stream_bridge.py        # LLM 청크 스트림을 async iterator로 브릿지
│   ├── ws_post_actions.py      # 세션 종료 후 비동기 작업 실행 (분석카드/욕구카드/태스크)
│   ├── ws_utils.py             # transcript 변환, 로그 마스킹, 안전 유틸리티
│   ├── greeting_service.py     # 오프닝 인사 문구 선택 (power-of-two-choices)
│   ├── close_policy.py         # [[CONFIRM_CLOSE]] 토큰 감지 및 종료 정책
│   ├── convo_policy.py         # 대화 턴 수 제한, 액티비티 턴 판정
│   ├── task_recommend.py       # 태스크 추천 컨텍스트 로드/저장
│   ├── task_llm_service.py     # 태스크 추천 LLM 호출
│   ├── task_generator.py       # 태스크 초안 생성 헬퍼
│   └── web_test_user.py        # 토큰 없을 때 웹 테스트용 익명/폴백 유저 처리
└── resources/
    ├── system_prompt.txt        # 감정 대화 시스템 프롬프트
    ├── task_prompt.txt          # 태스크(액티비티) 제안 프롬프트
    └── greeting_messages.txt    # 세션 오픈 시 서버가 먼저 보내는 인사 문구 목록
```

### 2.2 Analyze Service (`app/analyze/`)

감정 대화 세션의 transcript를 분석해 **분석카드(AnalysisCard)** 를 생성하고,
세션 만족도(SatisfactionRating)를 저장합니다.

```
app/analyze/
├── config.py             # 모델명/온도 등 설정 (app.core.llm_settings 사용)
├── schemas.py             # 카드/만족도 관련 Pydantic 스키마
├── models.py               # AnalysisCard, SatisfactionRating SQLModel
├── routers/
│   ├── cards.py            # /api/sessions, /api/cards 라우터
│   ├── satisfaction.py     # /api/sessions/{id}/satisfaction 라우터
│   └── summaries.py        # /api/summaries 라우터
└── services/
    ├── llm_card.py          # LLM을 통한 카드 생성 (JSON mode)
    ├── card_content.py      # 카드 본문이 "의미 있는 내용"인지 판정 (빈 카드 필터링)
    ├── prompt_loader.py     # 카드 생성용 프롬프트 로드
    ├── risk.py               # 위험 키워드 감지, 위험 레벨 판정 (LOW/MEDIUM/HIGH)
    └── summaries.py          # 요약 목록 조회 서비스
```

`app/analyze`는 자체 FastAPI 앱이나 DB 세션 팩토리를 갖지 않습니다 — DB는
`app/db/session.py`를 공유하고, 라우터는 `app/main.py`에서 prefix만 붙여 등록됩니다.

### 2.3 Desire Service (`app/desire/`)

대화 내용에서 **8가지 심리경제학적 욕구**를 분석하고, 사용자가 최종적으로 선택한
욕구(UserNeedSelection)를 저장합니다.

```
app/desire/
├── core/
│   ├── config.py               # 모델명 등 설정
│   ├── needs_definitions.py    # 8가지 욕구 코드·메타데이터(라벨/설명/해양생물) 정의
│   └── prompt_loader.py        # 욕구 분석 프롬프트 로드
├── models/
│   └── need_card.py            # NeedCardResult, NeedCardScore, UserNeedSelection SQLModel
├── schemas/
│   └── need_card.py             # 욕구 카드 요청/응답 Pydantic 스키마
├── crud/
│   └── need_card.py             # DB 조회/저장 함수 (히스토리, 마지막 선택 등)
├── routers/
│   └── need_card.py             # /need-cards/* 라우터
└── services/
    ├── need_analyzer.py         # LLM 욕구 분석 (0~100점 채점, 순위 도출)
    ├── llm_client.py             # desire 전용 LLM 클라이언트
    └── reflection_writer.py     # 개인화된 서술(reflection_message) 생성
```

### 2.4 Core (`app/core/`)

세 서비스가 공유하는 LLM 추상화 레이어와 설정입니다.

```
app/core/
├── llm_settings.py       # LLM_MODEL/TEMPERATURE/MAX_TOKENS/TIMEOUT 공용 로더 (레거시 이름 폴백 포함)
└── llm/
    ├── factory.py         # LLM_PROVIDER 값에 따라 프로바이더 생성
    ├── base.py             # BaseLLMProvider 추상 클래스
    ├── types.py            # 공용 타입 정의
    ├── providers.py        # 프로바이더 레지스트리
    ├── openai_provider.py     # OpenAI 구현체
    └── anthropic_provider.py  # Anthropic 구현체
```

### 2.5 DB (`app/db/`)

```
app/db/
├── session.py    # 엔진/세션 팩토리, DATABASE_URL 정규화, get_session/session_scope
└── health.py     # check_db_tables, health_db_response (/health/db에서 사용)
```

`CORE_REQUIRED_TABLES = (user, emotionsession, emotionstep)`,
`ANALYZE_REQUIRED_TABLES = CORE_REQUIRED_TABLES + (analysiscard,)` 로 정의되어
있으며, 시작 시 및 `/health/db`에서 이 테이블들의 존재 여부를 확인합니다.

---

## 3. 감정 대화 WebSocket 흐름

과거에는 클라이언트가 `MSG_OPEN`을 보내야 세션이 열렸지만, 현재는 **연결 직후
서버가 인증 토큰만으로 자동으로 세션을 열고, 사용자 입력 없이 먼저 인사 메시지를
보냅니다** (`app/backend/routers/emotion_ws.py`의 `_bootstrap_open_if_possible`).

```
Client                              Server
  │── WS connect (token) ─────────>│ 토큰 검증(쿼리/헤더/쿠키), 세션 자동 생성
  │<─ open_ok (session_id) ─────── │
  │                                 │ (1~2초 랜덤 딜레이 후)
  │<─ message_start ─────────────── │ 서버가 먼저 인사 문구 전송
  │<─ message (greeting text) ──── │ (greeting_service: power-of-two-choices 선택)
  │<─ message_end ──────────────── │
  │                                 │
  │── message (text) ─────────────>│ EmotionStep(user) 저장
  │<─ message_start ──────────────  │
  │<─ message_delta ... ──────────  │ LLM 스트리밍 응답 (60자 배치 전송)
  │<─ message ───────────────────── │ 전체 응답 텍스트
  │<─ message_end ────────────────  │ EmotionStep(assistant) 저장
  │                                 │
  │  (반복, 최대 SESSION_MAX_TURNS 턴, 특정 시점엔 task_recommend_ok 도 도착 가능) │
  │                                 │
  │── close 또는 [[CONFIRM_CLOSE]] 감지 ─→│ 세션 ended_at 기록
  │<─ close_ok ────────────────────  │ ↓ 비동기 실행
  │                                 │ · 분석카드 생성 (analyze)
  │                                 │ · 욕구카드 생성 (desire, 응답 알림 없음)
  │<─ analysis_card_ready(card) ── │ 또는 analysis_card_failed
  │                                 │
  │── ping ───────────────────────>│ 하트비트
  │<─ pong ────────────────────────  │
```

**핵심 변경점 (과거 문서 대비)**

1. `MSG_OPEN`은 이제 클라이언트가 보낼 필요가 없습니다 — 재전송해도 이미 열린
   `open_ok`를 다시 돌려줄 뿐입니다.
2. 스트리밍 메시지 타입은 `stream_chunk`/`stream_end`가 아니라
   `message_start` → `message_delta`(부분) → `message`(전체 텍스트) →
   `message_end` 입니다.
3. `close_confirm_needed` / `MSG_CONFIRM_CLOSE` 2단계 확인 흐름은 현재 라우터
   코드에서 사용되지 않습니다. `MSG_CLOSE`(또는 `[[CONFIRM_CLOSE]]` 자동 감지)가
   오면 바로 `finalize_close`가 실행되어 세션이 종료됩니다.
4. 세션 종료 시 **분석카드뿐 아니라 욕구카드(need card)도 자동 생성**됩니다
   (`ws_post_actions.generate_need_card_async`). 욕구카드 생성은 실패해도 소켓
   메시지를 별도로 보내지 않고 로그만 남깁니다.
5. 대화 중 "액티비티 턴"(`convo_policy.is_activity_turn`)으로 판단되면, 그
   턴의 응답 직후 태스크 추천이 자동 실행되어 `task_recommend_ok`가 옵니다 —
   `MSG_TASK_RECOMMEND`를 클라이언트가 명시적으로 보내지 않아도 됩니다.
6. `[[CONFIRM_CLOSE]]` 마커는 `user_order`가 `MIN_CLOSE_ORDER`(기본 16) 미만인
   이른 턴에서 감지되면 LLM 오발생으로 간주해 무시됩니다.

**자동 종료 조건**: 모델 응답 텍스트 마지막에 `[[CONFIRM_CLOSE]]` 문자열이
포함되면 서버가 이를 제거하고 세션을 자동으로 종료·분석합니다
(`close_policy.StreamingConfirmCloseFilter`가 청크 경계를 넘는 마커도 감지).

---

## 4. 인증 흐름

```
Client                              Server                         Google
  │── POST /auth/google ──────────────>│                               │
  │   {id_token: "..."}                │── GET tokeninfo?id_token ────>│
  │                                    │<─ {aud, iss, email, name} ───  │
  │                                    │ aud/iss 검증, User 없으면 auto-create │
  │                                    │ AccessToken 발급 (JWT_SECRET_KEY) │
  │                                    │ RefreshToken 발급 (JWT_REFRESH_SECRET, DB 저장) │
  │<── {access_token, ...} ─────────── │
  │    Set-Cookie: __Host-deepme_rtok  │
  │                                    │
  │  (ACCESS_TOKEN_EXPIRE_MINUTES 후 만료, 기본 120분) │
  │── POST /auth/refresh ─────────────>│ RefreshToken 검증
  │   Cookie: __Host-deepme_rtok       │ 토큰 rotation (새 토큰 발급)
  │<── {access_token} ─────────────── │ 이전 토큰 revoked_at 기록
```

Access Token 만료(`ACCESS_TOKEN_EXPIRE_MINUTES`)는 `app/backend/core/tokens.py`가
기본값 120분으로 읽습니다. `POST /auth/google`, `/auth/google/access`,
`GET /auth/callback` 세 경로 모두 동일하게 `_get_or_create_user` →
`issue_tokens_for_user`를 거칩니다.

**재사용 감지**: 이미 revoked된 RefreshToken으로 요청 시 해당 유저의 **모든
RefreshToken 일괄 삭제** (탈취 대응) — `app/backend/core/tokens.py` 참조.

---

## 5. LLM 프로바이더 추상화

```python
# app/core/llm/factory.py
def get_llm_provider() -> BaseLLMProvider:
    if settings.LLM_PROVIDER == "anthropic":
        return AnthropicProvider(...)
    return OpenAIProvider(...)  # 기본값

# 사용 예시 (llm_service.py)
provider = get_llm_provider()
async for chunk in provider.stream_chat(messages, ...):
    yield chunk
```

환경변수 `LLM_PROVIDER=anthropic`으로 전환 가능. 코드 변경 불필요.

모델명(`LLM_MODEL`)이 환경변수로 설정되지 않은 경우, backend/analyze/desire
세 서비스 모두 `app/core/llm_settings.get_llm_settings()`를 통해 각자의
`model_default` 인자값(현재 코드 기준 `gpt-5.4-mini-2026-03-17`)으로 폴백합니다.
`.env.example`의 `LLM_MODEL=gpt-4o-mini`는 어디까지나 예시값이며, 실제 기본
동작은 이 코드 폴백값을 따릅니다. `desire` 서비스는 `NEED_CARD_MODEL`(레거시
이름)로 개별 모델을 지정할 수 있습니다.

---

## 6. 데이터 흐름 요약

```
[WebSocket 연결]
    │
    ▼
서버가 세션 자동 생성 → 오프닝 인사 메시지 자동 전송 (GreetingMessageStat 카운터 갱신)
    │
    ▼
[사용자 입력] → EmotionStep(user) DB 저장
    │
    ▼
LLM 호출 (스트리밍) → EmotionStep(assistant) DB 저장
    │
    ├──> (액티비티 턴이면) 태스크 추천 자동 실행 → Task DB 저장 → task_recommend_ok 전송
    │
    ▼
세션 종료 (close 메시지 또는 [[CONFIRM_CLOSE]] 자동 감지)
    │
    ├──> EmotionSession.ended_at 기록
    │
    ├──> [비동기] analyze 서비스 호출
    │         → EmotionStep 읽기 → LLM JSON mode 카드 생성
    │         → risk.py 위험 레벨 판정 → AnalysisCard DB 저장
    │         → WS analysis_card_ready / analysis_card_failed 전송
    │
    └──> [비동기] desire 서비스 호출 (알림 없음)
              → NeedCardResult/NeedCardScore DB 저장
```
