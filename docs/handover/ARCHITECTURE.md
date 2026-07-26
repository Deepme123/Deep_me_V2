# 시스템 아키텍처

---

## 1. 전체 구조

Deep_me V2는 **Python 모노레포** 안에서 하나의 FastAPI 앱에 여러 서비스 패키지의
라우터를 붙이는 방식으로 동작합니다. `app/analyze`, `app/desire`는 별도로 마운트된
서브앱이 아니라, `app/backend/main.py`에서 만든 FastAPI 인스턴스에
`include_router(prefix=...)`로 라우터만 추가되는 구조입니다. 하나의 Uvicorn
프로세스가 하나의 PostgreSQL DB를 바라보며 모든 요청을 처리합니다.

```
┌───────────────────────────────────────────────────────────┐
│                   Uvicorn (Port 8000)                     │
│                                                           │
│  app/main.py                                             │
│  └── app.backend.main:app  ← 실제 FastAPI() 인스턴스       │
│       ├── /            backend 라우터 (인증, 감정대화 등)   │
│       ├── /analyze     app/analyze 라우터 include_router   │
│       └── /desire      app/desire 라우터 include_router    │
└───────────────────────────────────────────────────────────┘
         │                         │
    REST + WebSocket           PostgreSQL (app/db/session.py 단일 엔진)
```

---

## 2. 서비스별 역할

### 2.1 Backend Service (`app/backend/`)

핵심 서비스. 인증, 사용자, 감정 대화, 태스크를 담당합니다. `app/backend/main.py`가
실제 `FastAPI()` 앱을 생성하며, analyze/desire 라우터도 결국 이 앱에 붙습니다.

> QA용 서버 렌더링 데모(`demo_ui/`, `/demo/emotion-analysis`)는 제거되었습니다.

```
app/backend/
├── main.py              # FastAPI 앱 생성, CORS, 레이트리밋, 라우터 등록
├── core/
│   ├── tokens.py        # JWT 생성/검증, 리프레시 토큰 DB 저장/rotation
│   ├── jwt.py           # JWT 디코딩 헬퍼
│   ├── prompt_loader.py # backend 전용 시스템 프롬프트 로드 (resources/*.txt)
│   ├── logging_config.py # 로깅 설정, Discord 에러 알림 핸들러
│   └── rate_limit.py    # slowapi 레이트 리미터 설정
├── dependencies/
│   └── auth.py          # get_current_user 등 인증 Depends
├── models/
│   ├── user.py          # User SQLModel
│   ├── emotion.py       # EmotionSession SQLModel
│   ├── emotion_step.py  # EmotionStep SQLModel
│   ├── task.py          # Task SQLModel
│   └── refresh_token.py # RefreshToken SQLModel
├── schemas/
│   ├── emotion.py       # 감정 대화 요청/응답 Pydantic 스키마
│   └── task.py          # 태스크 스키마
├── routers/
│   ├── auth.py          # /auth/* (Google OAuth, 토큰 갱신/취소)
│   ├── emotion.py       # /emotion/* (세션, 스텝 REST API)
│   ├── emotion_ws.py    # /ws/emotion (WebSocket 핸들러)
│   ├── task.py          # /tasks/*
│   ├── health_llm.py    # /health/*
│   ├── user.py          # /users/*
│   └── deploy_webhook.py # GitHub → Render 배포 웹훅 + Discord 알림
├── services/
│   ├── llm_service.py       # LLM 추상화 레이어
│   ├── auth_service.py      # Google OAuth 토큰 검증, 유저 자동 생성
│   ├── ws_protocol.py       # WebSocket 메시지 파싱/토큰 추출
│   ├── ws_session_service.py # 세션 생명주기 관리
│   ├── ws_streaming.py      # 스트리밍 전송 버퍼(백프레셔)
│   ├── ws_post_actions.py   # 세션 종료 후 비동기 작업 실행(분석카드/태스크/욕구분석)
│   ├── ws_utils.py          # transcript 변환, 안전 유틸리티
│   ├── stream_bridge.py     # LLM 스트림 → WS 전송 브리지
│   ├── close_policy.py      # [[CONFIRM_CLOSE]] 토큰 감지 및 종료 정책
│   ├── convo_policy.py      # 대화 턴 수 제한, 액티비티 스텝 정책
│   ├── task_recommend.py    # 태스크 추천 컨텍스트 로드
│   ├── task_llm_service.py  # 태스크 추천 LLM 호출
│   ├── task_generator.py    # 태스크 생성 헬퍼
│   └── web_test_user.py     # 웹 테스트용 익명 유저 처리
└── resources/
    ├── system_prompt.txt    # 감정 대화 시스템 프롬프트
    └── task_prompt.txt      # 태스크 추천 프롬프트
```

### 2.2 Analyze Service (`app/analyze/`)

감정 대화 세션의 transcript를 분석해 **분석카드(AnalysisCard)** 를 생성합니다.
`app/db/session.py`의 공유 엔진을 사용하며(별도 `db.py`/`main.py` 없음), 라우터는
`app/main.py`에서 `/analyze` 프리픽스로 backend 앱에 붙습니다.

```
app/analyze/
├── config.py             # 모델명/온도 등 설정
├── schemas.py            # 카드/만족도 관련 Pydantic 스키마
├── models.py             # AnalysisCard(테이블명 analysiscard), SatisfactionRating
├── routers/
│   ├── cards.py          # /api/sessions, /api/cards 라우터
│   ├── satisfaction.py   # /api/sessions/{id}/satisfaction 라우터
│   └── summaries.py      # /api/summaries 라우터
├── services/
│   ├── llm_card.py       # LLM을 통한 카드 생성 (JSON mode)
│   ├── prompt_loader.py  # analyze 전용 카드 생성 프롬프트 로드
│   ├── card_content.py   # 카드 내용이 비어있는지 판정(빈 카드 필터링)
│   ├── risk.py           # 위험 키워드 감지, 위험 레벨 판정
│   └── summaries.py      # 요약 목록 조회 서비스
└── resources/
    └── card_system_prompt.txt  # 분석카드 생성 시스템 프롬프트
```

### 2.3 Desire Service (`app/desire/`)

대화 내용에서 **8가지 심리경제학적 욕구**를 분석하고, 유저별 선택 이력을 저장·조회합니다.

```
app/desire/
├── core/
│   ├── config.py        # 모델명 등 설정
│   ├── prompt_loader.py # desire 전용 reflection 프롬프트 로드
│   └── needs_definitions.py  # 8가지 욕구 코드·메타데이터 정의
├── models/
│   └── need_card.py     # NeedCardResult, NeedCardScore, UserNeedSelection SQLModel
├── schemas/
│   └── need_card.py     # 욕구 카드 스키마 (요청/응답 Pydantic)
├── crud/
│   └── need_card.py     # DB 조회/저장 함수 (히스토리, 마지막 선택 등)
├── routers/
│   └── need_card.py     # /need-cards/* 라우터
├── services/
│   ├── need_analyzer.py     # LLM 욕구 분석 (0~100점 채점, 순위·근거 도출)
│   ├── reflection_writer.py # top4 욕구별 개인화 reflection 문단 생성
│   └── llm_client.py        # desire 전용 LLM 클라이언트
└── resources/
    ├── reflection_system_prompt.txt  # reflection 생성 시스템 프롬프트
    └── reflection_user_prompt.txt    # reflection 생성 유저 프롬프트 템플릿
```

### 2.4 Core (`app/core/`) / 공유 DB (`app/db/`)

`app/core/`는 세 서비스가 공유하는 LLM 추상화 레이어입니다. 별도의
`settings.py`(pydantic-settings)는 없고, `llm_settings.py`가 환경변수를 직접
읽어 호출별 기본값·레거시 이름 폴백을 적용합니다.

```
app/core/
├── llm_settings.py      # LLM_MODEL/TEMPERATURE/MAX_TOKENS/TIMEOUT 등 환경변수 읽기
└── llm/
    ├── factory.py       # LLM_PROVIDER 값에 따라 프로바이더 생성
    ├── base.py          # BaseLLMProvider 추상 클래스
    ├── openai_provider.py    # OpenAI 구현체
    └── anthropic_provider.py # Anthropic 구현체
```

`app/db/`는 세 패키지가 공유하는 단일 DB 엔진/세션 팩토리입니다.

```
app/db/
├── session.py  # DATABASE_URL 정규화, get_engine/get_session/session_scope
└── health.py   # check_db_tables, health_db_response (/health/db에서 사용)
```

---

## 3. 감정 대화 WebSocket 흐름

```
Client                              Server
  │                                    │
  │── MSG_OPEN (token) ───────────────>│ 인증, 세션 생성/복원
  │<─ open_ok ──────────────────────── │
  │                                    │
  │── MSG_MESSAGE (text) ─────────────>│ EmotionStep(user) 저장
  │<─ stream chunk ... ─────────────── │ LLM 스트리밍 응답
  │<─ stream_end ───────────────────── │ EmotionStep(assistant) 저장
  │                                    │
  │  (반복, 최대 POLICY_MAX_TURNS 턴)  │  ← 레거시 이름 SESSION_MAX_TURNS도 폴백으로 지원
  │                                    │
  │── MSG_CLOSE ──────────────────────>│ 종료 의사 확인 요청
  │<─ close_confirm_needed ──────────── │
  │                                    │
  │── MSG_CONFIRM_CLOSE ──────────────>│ 세션 ended_at 기록
  │<─ close_ok ──────────────────────── │
  │                                    │ ↓ 비동기 실행 (ws_post_actions.py)
  │                                    │ · 분석카드 생성 (analyze 서비스)
  │                                    │ · 욕구(need-card) 분석 생성 (desire 서비스)
  │                                    │ · 태스크 추천
  │                                    │
  │<─ analysis_card_ready (card data) ─ │ 카드 생성 완료 통지
  │                                    │
  │── MSG_PING ───────────────────────>│ 하트비트
  │<─ MSG_PONG ──────────────────────── │
```

**자동 종료 조건**: 모델 응답 텍스트 마지막에 `[[CONFIRM_CLOSE]]` 문자열이 포함되면 서버가 자동으로 세션을 종료하고 분석을 트리거합니다.

---

## 4. 인증 흐름

```
Client                              Server                         Google
  │                                    │                               │
  │── POST /auth/google ──────────────>│                               │
  │   {id_token: "..."}                │── GET tokeninfo?id_token ────>│
  │                                    │<─ {sub, email, name} ────────  │
  │                                    │ User 없으면 auto-create        │
  │                                    │ AccessToken(120분) 발급        │
  │                                    │ RefreshToken(21일) DB 저장     │
  │<── {access_token, ...} ─────────── │
  │    Set-Cookie: __Host-deepme_rtok  │
  │                                    │
  │  (120분 후 AccessToken 만료)       │
  │── POST /auth/refresh ─────────────>│ RefreshToken 검증
  │   Cookie: __Host-deepme_rtok       │ 토큰 rotation (새 토큰 발급)
  │<── {access_token} ─────────────── │ 이전 토큰 revoked_at 기록
```

**재사용 감지**: 이미 revoked된 RefreshToken으로 요청 시 해당 유저의 **모든 RefreshToken 일괄 삭제** (탈취 대응)

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

---

## 6. 데이터 흐름 요약

```
[사용자 입력]
    │
    ▼
WebSocket 수신 → EmotionStep(user) DB 저장
    │
    ▼
LLM 호출 (스트리밍) → EmotionStep(assistant) DB 저장
    │
    ▼
세션 종료 (confirm_close 또는 [[CONFIRM_CLOSE]])
    │
    ├──> EmotionSession.ended_at 기록
    │
    ├──> [비동기] analyze 서비스 호출
    │         → EmotionStep 읽기
    │         → LLM JSON mode 카드 생성
    │         → risk.py 위험 레벨 판정
    │         → AnalysisCard DB 저장 (테이블명 analysiscard)
    │         → WS analysis_card_ready 전송
    │
    ├──> [비동기] desire 서비스 호출 (generate_need_card_async)
    │         → EmotionStep(user/assistant) transcript 조합
    │         → LLM 8가지 욕구 채점 + 근거(rationale) 생성
    │         → top4 욕구에 reflection_writer로 개인화 문단 생성
    │         → NeedCardResult / NeedCardScore DB 저장
    │
    └──> [비동기] task_recommend 호출
              → 감정 맥락 분석
              → 1~5개 실천 과제 생성
              → Task DB 저장
```
