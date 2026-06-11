# 시스템 아키텍처

---

## 1. 전체 구조

Deep_me V2는 **Python 모노레포** 안에서 여러 FastAPI 서비스를 마운트하는 방식으로 동작합니다.  
하나의 Uvicorn 프로세스가 모든 서비스를 처리합니다.

```
┌─────────────────────────────────────────────────────┐
│                   Uvicorn (Port 8000)               │
│                                                     │
│  app/main.py  ← 모든 서비스를 마운트하는 진입점          |
│  ├── /           app/backend/main.py  (메인 API)     │
│  ├── /analyze    app/analyze/main.py  (분석카드)      │
│  └── /desire     app/desire/main.py   (욕구분석)      │
└─────────────────────────────────────────────────────┘
         │                         │
    REST + WebSocket           PostgreSQL
```

---

## 2. 서비스별 역할

### 2.1 Backend Service (`app/backend/`)

핵심 서비스. 인증, 사용자, 감정 대화, 태스크를 담당합니다.

```
app/backend/
├── main.py              # FastAPI 앱 생성, 라우터 등록, CORS 설정
├── core/
│   ├── tokens.py        # JWT 생성/검증, 리프레시 토큰 DB 저장
│   ├── jwt.py           # JWT 디코딩 헬퍼
│   ├── prompt_loader.py # 시스템 프롬프트 로드 (resources/*.txt)
│   └── prompt_loader.py
├── models/
│   ├── user.py          # User SQLModel
│   ├── emotion.py       # EmotionSession, EmotionStep SQLModel
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
│   ├── deploy_webhook.py # 배포 웹훅
│   └── demo.py          # /demo/emotion-analysis (QA HTML UI)
├── services/
│   ├── llm_service.py       # LLM 추상화 레이어
│   ├── ws_protocol.py       # WebSocket 메시지 파싱/토큰 추출
│   ├── ws_session_service.py # 세션 생명주기 관리
│   ├── ws_streaming.py      # 스트리밍 전송 버퍼(백프레셔)
│   ├── ws_post_actions.py   # 세션 종료 후 비동기 작업 실행
│   ├── ws_utils.py          # transcript 변환, 안전 유틸리티
│   ├── close_policy.py      # [[CONFIRM_CLOSE]] 토큰 감지 및 종료 정책
│   ├── convo_policy.py      # 대화 턴 수 제한, 액티비티 스텝 정책
│   ├── task_recommend.py    # 태스크 추천 컨텍스트 로드
│   ├── task_llm_service.py  # 태스크 추천 LLM 호출
│   └── web_test_user.py     # 웹 테스트용 익명 유저 처리
├── resources/
│   ├── system_prompt.txt    # 감정 대화 시스템 프롬프트
│   └── task_recommend_prompt.txt
└── demo_ui/                 # QA 테스트용 HTML/CSS/JS
```

### 2.2 Analyze Service (`app/analyze/`)

감정 대화 세션의 transcript를 분석해 **분석카드(AnalysisCard)** 를 생성합니다.

```
app/analyze/
├── main.py              # 서브 FastAPI 앱
├── db.py                # analyze 전용 DB 세션
├── config.py            # 모델명/온도 등 설정
├── schemas.py           # 카드 관련 Pydantic 스키마
├── models.py            # AnalysisCard SQLModel (DB 테이블명: emotioncard)
├── routers/
│   ├── cards.py         # /api/sessions, /api/cards 라우터
│   └── summaries.py     # /api/summaries 라우터
└── services/
    ├── llm_card.py      # LLM을 통한 카드 생성 (JSON mode)
    ├── risk.py          # 위험 키워드 감지, 위험 레벨 판정
    └── summaries.py     # 요약 목록 조회 서비스
```

### 2.3 Desire Service (`app/desire/`)

대화 내용에서 **8가지 심리경제학적 욕구**를 분석합니다.

```
app/desire/
├── main.py              # 서브 FastAPI 앱
├── core/
│   ├── config.py        # 모델명 등 설정
│   └── needs_definitions.py  # 8가지 욕구 코드·메타데이터 정의
├── models/
│   └── need_card.py     # NeedCardResult, NeedCardScore SQLModel
├── schemas/
│   └── need_card.py     # 욕구 카드 스키마 (요청/응답 Pydantic)
├── crud/
│   └── need_card.py     # DB 조회/저장 함수
├── routers/
│   └── need_card.py     # /need-cards/* 라우터
└── services/
    ├── need_analyzer.py # LLM 욕구 분석 (0~100점 채점, 순위 도출)
    └── llm_client.py    # desire 전용 LLM 클라이언트
```

### 2.4 Core (`app/core/`)

여러 서비스가 공유하는 LLM 추상화 레이어와 설정입니다.

```
app/core/
├── settings.py          # pydantic-settings (환경변수 → Settings 객체)
└── llm/
    ├── factory.py       # LLM_PROVIDER 값에 따라 프로바이더 생성
    ├── base.py          # BaseLLMProvider 추상 클래스
    ├── openai_provider.py    # OpenAI 구현체
    └── anthropic_provider.py # Anthropic 구현체
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
  │  (반복, 최대 SESSION_MAX_TURNS 턴) │
  │                                    │
  │── MSG_CLOSE ──────────────────────>│ 종료 의사 확인 요청
  │<─ close_confirm_needed ──────────── │
  │                                    │
  │── MSG_CONFIRM_CLOSE ──────────────>│ 세션 ended_at 기록
  │<─ close_ok ──────────────────────── │
  │                                    │ ↓ 비동기 실행
  │                                    │ · 분석카드 생성 (analyze 서비스)
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
    │         → EmotionCard DB 저장
    │         → WS analysis_card_ready 전송
    │
    └──> [비동기] task_recommend 호출
              → 감정 맥락 분석
              → 1~5개 실천 과제 생성
              → Task DB 저장
```
