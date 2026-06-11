# API 레퍼런스

모든 엔드포인트 기준 URL: `http://localhost:8000` (로컬)

---

## 1. 인증 (`/auth`)

### `GET /auth/login/google`

Google OAuth 로그인 페이지로 리디렉트합니다. 웹 브라우저 기반 로그인 흐름.

---

### `GET /auth/callback`

Google OAuth 콜백 처리. `code`를 받아 AT/RT를 발급합니다.

**Response:**
```json
{
  "access_token": "JWT_액세스_토큰",
  "token_type": "bearer",
  "expires_in": 43200,
  "user": { "user_id": "uuid", "name": "홍길동", "email": "user@gmail.com" }
}
```

---

### `POST /auth/google`

Google ID 토큰으로 로그인합니다. 모바일/SPA 권장 방식. 사용자 없으면 자동 생성.

**Request:**
```json
{ "id_token": "Google_ID_토큰" }
```

**Response:**
```json
{
  "access_token": "JWT_액세스_토큰",
  "token_type": "bearer",
  "expires_in": 43200,
  "user": { "user_id": "uuid", "name": "홍길동", "email": "user@gmail.com" }
}
```

리프레시 토큰은 `Set-Cookie: __Host-deepme_rtok` 헤더로 전달됩니다.

---

### `POST /auth/google/access`

Google Access 토큰으로 로그인합니다.

**Request:**
```json
{ "access_token": "Google_액세스_토큰" }
```

---

### `POST /auth/refresh`

액세스 토큰을 갱신합니다. RT rotation 방식 — 매 갱신마다 새 RT 발급, 이전 RT 폐기.

**Request:** 쿠키 `__Host-deepme_rtok` 필요 (body 없음)

**Response:**
```json
{ "access_token": "새_JWT", "token_type": "bearer", "expires_in": 43200, "user_id": "uuid" }
```

---

### `GET /auth/logout`

현재 사용자의 모든 RT 무효화 + 쿠키 제거.

**Response:** `{ "ok": true }`

---

## 2. 감정 대화 REST (`/emotion`)

모든 엔드포인트는 인증 선택적 (`Authorization: Bearer {token}` 없으면 웹 테스트용 익명 유저로 처리).

### `POST /emotion/sessions`

새 감정 세션을 생성합니다.

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

**Response:** EmotionSession 배열 (started_at 내림차순)

---

### `GET /emotion/steps`

특정 세션의 대화 transcript를 조회합니다.

**Query:** `?session_id={uuid}&limit=50&offset=0`

**Response:** EmotionStep 배열 (step_order 오름차순)

---

### `POST /emotion/steps`

대화 스텝을 수동으로 저장합니다 (내부/테스트용).

**Request:**
```json
{
  "session_id": "uuid",
  "step_order": 1,
  "step_type": "user",
  "user_input": "오늘 많이 힘들었어요",
  "gpt_response": ""
}
```

---

### `POST /emotion/steps/generate`

스트리밍 없이 AI 응답을 생성하고 DB에 저장합니다 (테스트/내부용).

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
→ 세션 종료 + 분석카드 자동 생성 + 태스크 추천 트리거

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
    "risk_level": "LOW"
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

모든 엔드포인트는 `Authorization: Bearer {token}` 필요. 다른 유저 리소스 접근 시 403.

### `POST /analyze/api/sessions`

분석 전용 세션을 생성합니다.

---

### `POST /analyze/api/sessions/{session_id}/cards/auto-from-session`

저장된 EmotionStep transcript로 분석카드를 자동 생성합니다.  
**현재 실제로 사용되는 핵심 엔드포인트입니다.** WebSocket `confirm_close` 후 자동 호출됨.

**Request:** body 없음

**Response:**
```json
{
  "card_id": "uuid",
  "session_id": "uuid",
  "summary": "오늘 직장에서 받은 압박감으로 인해...",
  "core_emotions": [{"label": "불안", "intensity": 8}, {"label": "무력감", "intensity": 6}],
  "situation": "상사로부터 갑작스러운 질책을 받음",
  "situation_steps": [...],
  "physical_reactions": [...],
  "behavior_patterns": [...],
  "coping_actions": [...],
  "tags": ["직장스트레스", "자존감"],
  "insight": "...",
  "risk_flag": false,
  "risk_level": "LOW",
  "exportable": true,
  "created_at": "2026-01-01T00:00:00"
}
```

---

### `POST /analyze/api/sessions/{session_id}/cards/auto`

conversation_log를 직접 보내서 카드를 생성합니다 (DB transcript 불필요).

**Request:**
```json
{
  "conversation_log": [
    {"role": "user", "speaker": "USER", "text": "..."},
    {"role": "assistant", "speaker": "NOA", "text": "..."}
  ],
  "title_hint": "선택적 힌트"
}
```

---

### `POST /analyze/api/sessions/{session_id}/cards`

카드를 수동으로 생성합니다 (내부/테스트용).

---

### `GET /analyze/api/sessions/{session_id}/cards`

세션의 분석카드 목록을 조회합니다. (created_at 내림차순)

---

### `GET /analyze/api/cards/{card_id}`

분석카드 한 건을 조회합니다.

---

### `GET /analyze/api/summaries`

전체 요약 목록을 조회합니다.

**Query:** `?limit=20&offset=0`

---

### `GET /analyze/api/sessions/{session_id}/summaries`

특정 세션의 요약 목록을 조회합니다.

**Query:** `?limit=20&offset=0`

---

## 5. 욕구 분석 (`/desire/need-cards`)

### `GET /desire/need-cards/list`

8가지 욕구 전체 목록과 메타데이터를 반환합니다.

**Response:**
```json
{
  "needs": [
    {
      "code": "Meaning",
      "label_ko": "의미",
      "label_en": "Meaning",
      "description": "행동과 노력이 가치 있고 의미 있다고 느끼고 싶음.",
      "icon": "meaning"
    },
    ...
  ]
}
```

---

### `POST /desire/need-cards/analyze`

대화 내용에서 8가지 욕구를 분석하고 DB에 저장합니다.

**Request:**
```json
{
  "session_id": "uuid",
  "conversation_text": "오늘 회사에서 인정받지 못한 것 같아서..."
}
```

**Response:**
```json
{
  "needs": [
    {
      "code": "Meaning",
      "label_ko": "의미",
      "label_en": "Meaning",
      "score": 85,
      "rank": 1,
      "creature_name_ko": "거북이",
      "creature_emoji": "🐢",
      "creature_description": "오래 사는 존재 — 인내, 지속성, 깊은 방향감"
    },
    ...
  ],
  "top4": [...]
}
```

**8가지 욕구 코드 및 해양생물 매핑:**

| 코드 | 한국어 | 해양생물 | 이모지 |
|------|--------|---------|--------|
| `Together` | 소속감 | 물고기 무리 | 🐠 |
| `Safe` | 안전 | 불가사리 | ⭐ |
| `Choice` | 자율 | 해마 | 🌊 |
| `Meaning` | 의미 | 거북이 | 🐢 |
| `Peace` | 평온 | 수달 | 🦦 |
| `Grow` | 성장 | 해파리 | 🪼 |
| `True` | 진정성 | 조개 | 🐚 |
| `Fun` | 재미 | 문어 | 🐙 |

> `score`: 0~100. `rank`: 1=가장 높은 욕구, 8=가장 낮은 욕구.

---

### `GET /desire/need-cards/results/{session_id}`

세션에 저장된 욕구 분석 결과를 조회합니다. **홈 화면에서 선택한 욕구카드 표시에 사용.**

**Response:**
```json
{
  "result_id": "uuid",
  "session_id": "uuid",
  "created_at": "2026-01-01T00:00:00",
  "needs": [
    {
      "code": "Meaning",
      "label_ko": "의미",
      "label_en": "Meaning",
      "score": 85,
      "rank": 1,
      "creature_name_ko": "거북이",
      "creature_emoji": "🐢",
      "creature_description": "오래 사는 존재 — 인내, 지속성, 깊은 방향감"
    },
    ...
  ],
  "top4": [...]
}
```

결과 없으면 `404`.

---

### `POST /desire/need-cards/selection`

선택된 욕구 코드 목록의 UI 렌더링 메타데이터를 반환합니다. DB 저장 없음.

**Request:**
```json
{ "selected_needs": ["Meaning", "Together"] }
```

**Response:**
```json
{
  "needs": [
    {
      "code": "Meaning",
      "label_ko": "의미",
      "label_en": "Meaning",
      "description": "행동과 노력이 가치 있고 의미 있다고 느끼고 싶음.",
      "icon": "meaning",
      "creature_name_ko": "거북이",
      "creature_emoji": "🐢",
      "creature_description": "오래 사는 존재 — 인내, 지속성, 깊은 방향감"
    }
  ]
}
```

---

## 6. 태스크 (`/tasks`)

모든 엔드포인트는 `Authorization: Bearer {token}` 필요.

### `GET /tasks`

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

### `GET /tasks/{task_id}`

태스크 한 건을 조회합니다.

---

### `PATCH /tasks/{task_id}`

태스크 제목/설명을 수정합니다.

**Request:**
```json
{ "title": "수정된 제목", "description": "수정된 설명" }
```

---

### `PATCH /tasks/{task_id}/complete`

태스크를 완료 처리합니다. `is_completed = true`, `completed_at` 기록.

---

### `DELETE /tasks/{task_id}`

태스크를 삭제합니다.

**Response:** `{ "ok": true }`

---

### `POST /tasks/gpt`

LLM이 일반 프롬프트 기반으로 태스크를 추천·생성합니다.

---

### `POST /tasks/gpt/by-session`

특정 세션의 대화 내용을 기반으로 LLM이 태스크를 추천·생성합니다.

**Request:**
```json
{
  "session_id": "uuid",
  "n": 3,
  "recent_steps_limit": 20,
  "max_history_chars": 3000
}
```

**Response:** 생성된 Task 배열

---

## 7. 헬스체크 (`/health`)

| 엔드포인트 | 설명 |
|------------|------|
| `GET /health` | 기본 상태 확인 |
| `GET /health/db` | DB 연결 확인 |
| `GET /health/llm` | LLM 응답 확인 (blocking) |
| `GET /health/llm/stream` | LLM 스트리밍 확인 |

---

## 8. QA Demo UI

`GET /demo/emotion-analysis` — HTML 페이지 반환 (Vanilla JS WebSocket 테스트 UI)

회귀 테스트 및 내부 QA용. 운영 UI와 별개입니다.

---

## 9. 공통 에러 응답

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
| `502` | LLM 응답 생성 실패 |
