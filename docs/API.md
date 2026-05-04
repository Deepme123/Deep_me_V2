# API 레퍼런스

모든 엔드포인트 기준 URL: `http://localhost:8000` (로컬)

---

## 1. 인증 (`/auth`)

### `POST /auth/google-id-token`

Google ID 토큰으로 로그인합니다. 사용자가 없으면 자동 생성됩니다.

**Request:**
```json
{ "id_token": "Google_ID_토큰" }
```

**Response:**
```json
{
  "access_token": "JWT_액세스_토큰",
  "token_type": "bearer",
  "expires_in": 7200
}
```
리프레시 토큰은 `Set-Cookie: __Host-deepme_rtok` 헤더로 전달됩니다.

---

### `POST /auth/google-access-token`

Google Access 토큰으로 로그인합니다.

**Request:**
```json
{ "access_token": "Google_액세스_토큰" }
```

---

### `POST /auth/refresh`

액세스 토큰을 갱신합니다. 리프레시 토큰은 쿠키에서 자동으로 읽습니다.

**Request:** 쿠키 `__Host-deepme_rtok` 필요 (body 없음)

**Response:**
```json
{ "access_token": "새_JWT", "token_type": "bearer", "expires_in": 7200 }
```

> 리프레시 토큰 rotation: 매 갱신마다 새 리프레시 토큰 발급, 이전 토큰 폐기

---

### `POST /auth/logout`

현재 리프레시 토큰을 폐기합니다.

**Request:** 쿠키 필요

**Response:** `204 No Content`

---

## 2. 감정 대화 REST (`/emotion`)

### `POST /emotion/sessions`

새 감정 세션을 생성합니다.

**Headers:** `Authorization: Bearer {access_token}`

**Response:**
```json
{
  "session_id": "uuid",
  "user_id": "uuid",
  "started_at": "2026-01-01T00:00:00"
}
```

---

### `GET /emotion/sessions`

사용자의 세션 목록을 조회합니다.

**Query:** `?limit=20&offset=0`

**Response:** 세션 배열

---

### `GET /emotion/steps`

특정 세션의 대화 transcript를 조회합니다.

**Query:** `?session_id={uuid}`

**Response:** EmotionStep 배열 (step_order 오름차순)

---

### `POST /emotion/steps/generate`

스트리밍 없이 AI 응답을 생성합니다 (테스트/내부용).

**Request:**
```json
{
  "session_id": "uuid",
  "user_input": "오늘 많이 힘들었어요"
}
```

---

## 3. 감정 대화 WebSocket (`/ws/emotion`)

WebSocket 연결 주소: `ws://localhost:8000/ws/emotion`

### 인증 방법 (3가지 중 하나 선택)

```
1. 쿼리 파라미터: ws://localhost:8000/ws/emotion?token=액세스_토큰
2. Authorization 헤더: Bearer 토큰
3. 쿠키: __Host-deepme_rtok
```

---

### 클라이언트 → 서버 메시지

#### `MSG_OPEN` — 핸드셰이크

```json
{
  "type": "open",
  "token": "액세스_토큰",
  "session_id": "기존_세션_UUID_또는_null"
}
```

#### `MSG_MESSAGE` — 사용자 발화

```json
{
  "type": "message",
  "text": "오늘 정말 힘들었어요"
}
```

#### `MSG_CLOSE` — 종료 요청

```json
{ "type": "close" }
```

#### `MSG_CONFIRM_CLOSE` — 종료 확정

```json
{ "type": "confirm_close" }
```
→ 세션 종료 + 분석카드 생성 + 태스크 추천 트리거

#### `MSG_CANCEL_CLOSE` — 종료 취소

```json
{ "type": "cancel_close" }
```

#### `MSG_TASK_RECOMMEND` — 태스크 추천 요청

```json
{ "type": "task_recommend" }
```

#### `MSG_PING` — 하트비트

```json
{ "type": "ping" }
```

---

### 서버 → 클라이언트 메시지

#### `open_ok`

```json
{
  "type": "open_ok",
  "session_id": "uuid",
  "step_count": 4
}
```

#### 스트리밍 응답 청크

```json
{ "type": "stream_chunk", "text": "안녕하세요," }
{ "type": "stream_chunk", "text": " 오늘..." }
{ "type": "stream_end", "full_text": "안녕하세요, 오늘..." }
```

#### `close_confirm_needed`

```json
{ "type": "close_confirm_needed" }
```

#### `close_ok`

```json
{ "type": "close_ok", "session_id": "uuid" }
```

#### `analysis_card_ready`

```json
{
  "type": "analysis_card_ready",
  "card": {
    "card_id": "uuid",
    "summary": "...",
    "core_emotions": ["불안", "외로움"],
    "situation": "...",
    "risk_flag": false,
    "risk_level": "LOW",
    ...
  }
}
```

#### `analysis_card_failed`

```json
{ "type": "analysis_card_failed", "reason": "timeout" }
```

#### `pong`

```json
{ "type": "pong" }
```

---

## 4. 분석카드 (`/analyze/api`)

### `POST /analyze/api/sessions`

분석 전용 세션을 생성합니다.

**Request:**
```json
{ "source_session_id": "emotion_session_uuid" }
```

---

### `POST /analyze/api/sessions/{session_id}/cards/auto-from-session`

저장된 EmotionStep transcript로 분석카드를 자동 생성합니다.  
**현재 실제로 사용되는 핵심 엔드포인트입니다.**

**Request:** body 없음 (session_id가 이미 DB에 저장된 transcript를 가리킴)

**Response:**
```json
{
  "card_id": "uuid",
  "session_id": "uuid",
  "summary": "오늘 직장에서 받은 압박감으로 인해...",
  "core_emotions": ["불안", "무력감"],
  "situation": "상사로부터 갑작스러운 질책을 받음",
  "emotion": "불안과 수치심이 교차함",
  "thoughts": "나는 능력이 없는 것 같다",
  "physical_reactions": "가슴이 답답하고 두통",
  "behaviors": "퇴근 후 아무것도 못 함",
  "coping_actions": [...],
  "risk_flag": false,
  "risk_level": "LOW",
  "tags": ["직장스트레스", "자존감"],
  "insight": "..."
}
```

---

### `POST /analyze/api/sessions/{session_id}/cards/auto`

conversation_log를 직접 보내서 카드를 생성합니다 (DB transcript 불필요).

**Request:**
```json
{
  "conversation_log": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

---

### `GET /analyze/api/sessions/{session_id}/cards`

세션의 분석카드 목록을 조회합니다.

---

### `GET /analyze/api/cards/{card_id}`

분석카드 한 건을 조회합니다.

---

## 5. 욕구 분석 (`/desire/need-cards`)

### `POST /desire/need-cards/analyze`

대화 내용에서 8가지 욕구를 분석합니다.

**Request:**
```json
{ "conversation_text": "오늘 회사에서 인정받지 못한 것 같아서..." }
```

**Response:**
```json
{
  "all_needs": [
    {
      "need_code": "RECOGNITION",
      "label": "인정/지위",
      "score": 85,
      "rank": 1,
      "summary": "인정받고 싶은 욕구가 강하게 나타남"
    },
    ...  // 8개 전체
  ],
  "top_needs": [...]  // 상위 4개
}
```

**8가지 욕구 코드:**

| 코드 | 한국어 |
|------|--------|
| `CONNECTION` | 연결/소속 |
| `AUTONOMY` | 자율성 |
| `COMPETENCE` | 유능감/성취 |
| `RECOGNITION` | 인정/지위 |
| `SAFETY` | 안전/안정 |
| `NOVELTY` | 새로움/성장 |
| `PLEASURE` | 즐거움/기쁨 |
| `MEANING` | 의미/목적 |

---

### `POST /desire/need-cards/selection`

선택된 욕구 코드의 UI 렌더링 메타데이터를 반환합니다.

**Request:**
```json
{ "selected_needs": ["RECOGNITION", "AUTONOMY"] }
```

---

## 6. 태스크 (`/tasks`)

### `GET /tasks`

**Headers:** `Authorization: Bearer {token}`

사용자의 태스크 목록을 반환합니다.

---

### `POST /tasks`

태스크를 생성합니다.

**Request:**
```json
{
  "title": "오늘 저녁 10분 산책하기",
  "description": "감정 환기를 위한 가벼운 산책"
}
```

---

### `PUT /tasks/{task_id}`

태스크 완료 상태를 업데이트합니다.

**Request:**
```json
{ "is_completed": true }
```

---

## 7. 헬스체크 (`/health`)

| 엔드포인트 | 설명 |
|------------|------|
| `GET /health` | 기본 상태 확인 |
| `GET /health/db` | DB 연결 확인 |
| `GET /health/llm` | LLM 응답 확인 (blocking) |
| `GET /health/llm/stream` | LLM 스트리밍 확인 |

---

## 8. 프롬프트 관리 (`/prompts`)

### `GET /prompts/system`

현재 시스템 프롬프트를 반환합니다.

### `PUT /prompts/system`

시스템 프롬프트를 업데이트합니다.

**Request:**
```json
{ "content": "새 시스템 프롬프트 내용" }
```

---

## 9. QA Demo UI

`GET /demo/emotion-analysis` — HTML 페이지 반환 (Vanilla JS WebSocket 테스트 UI)  

회귀 테스트 및 내부 QA용으로 유지됩니다. 운영 UI와 별개입니다.

---

## 10. 공통 에러 응답

```json
{ "detail": "에러 메시지" }
```

| 코드 | 의미 |
|------|------|
| `400` | 잘못된 요청 파라미터 |
| `401` | 인증 필요 또는 토큰 만료 |
| `403` | 권한 없음 (다른 사용자 리소스 접근) |
| `404` | 리소스 없음 |
| `422` | Pydantic 유효성 검사 실패 |
| `500` | 서버 내부 오류 |
