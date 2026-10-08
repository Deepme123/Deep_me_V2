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

Google ID 토큰으로 로그인합니다. 모바일/SPA 권장 방식. `aud`/`iss` 검증 후,
사용자 없으면 자동 생성.

**Request:**
```json
{ "id_token": "Google_ID_토큰" }
```

**Response:** `GET /auth/callback`과 동일한 형태.

리프레시 토큰은 `Set-Cookie: __Host-deepme_rtok` 헤더로 전달됩니다.

---

### `POST /auth/google/access`

Google Access 토큰으로 로그인합니다 (userinfo 엔드포인트 조회, scope에
`openid email profile` 필요).

**Request:**
```json
{ "access_token": "Google_액세스_토큰" }
```

---

### `POST /auth/refresh`

액세스 토큰을 갱신합니다. RT rotation 방식 — 매 갱신마다 새 RT 발급, 이전 RT 폐기.
이미 revoked된 RT가 재사용되면 해당 유저의 모든 RT가 무효화됩니다.

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

모든 엔드포인트는 `Authorization: Bearer {token}` 인증이 필요합니다. 단,
환경변수 `EMOTION_NO_AUTH_WEB_TEST=true`로 설정된 경우에만 토큰 없이도
결정론적인 웹 테스트용 익명 유저(`WEB_TEST_USER_EMAIL`)로 폴백합니다
(`web_test_user.resolve_emotion_user_id`) — 기본값은 `false`이므로 토큰이
없으면 `401`입니다.

### `GET /emotion/sessions/active`

현재 진행 중(`ended_at IS NULL`)인 세션 중 가장 최근 것을 대화 내역과 함께
반환합니다. 없으면 `404`.

**Response:**
```json
{ "session": { "session_id": "uuid", "...": "..." }, "steps": [ { "...": "..." } ] }
```

---

### `GET /emotion/sessions`

사용자의 세션 목록을 조회합니다. 사용자 발화가 하나도 없는 빈 세션, 그리고
진행 중이면서 분석카드도 없는 세션은 목록에서 제외됩니다.

**Query:** `?limit=20&offset=0`

**Response:** EmotionSession 배열 (started_at 내림차순)

---

### `GET /emotion/sessions/{session_id}`

세션 한 건을 조회합니다. 다른 유저 소유면 `404`.

---

### `GET /emotion/steps`

특정 세션의 대화 transcript를 조회합니다.

**Query:** `?session_id={uuid}&limit=50&offset=0`

**Response:** EmotionStep 배열 (step_order 오름차순)

---

### `POST /emotion/sessions`

새 감정 세션을 생성합니다 (내부/테스트용 — 실제 세션 오픈은 WebSocket 연결
시 서버가 자동으로 처리합니다. 아래 3장 참조).

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

스트리밍 없이 AI 응답을 생성하고 DB에 저장합니다 (테스트/내부용). 액티비티
턴으로 판정되면 태스크 프롬프트가 함께 적용되고 마커 스텝이 추가됩니다.

**Request:**
```json
{
  "session_id": "uuid",
  "step_type": "user",
  "user_input": "오늘 많이 힘들었어요"
}
```

---

## 3. 감정 대화 WebSocket (`/ws/emotion`)

WebSocket 연결 주소: `ws://localhost:8000/ws/emotion`

### 인증 방법 (3가지 중 하나 선택)

```
1. 쿼리 파라미터: ws://localhost:8000/ws/emotion?access_token=액세스_토큰 (또는 token, auth_token)
2. Authorization 헤더: Bearer 토큰
3. 쿠키: access_token
```

인증 토큰이 없으면 연결이 `4401`로 거부됩니다(`auth_required`). 토큰은 있지만
무효하면 `4401`(`invalid_token`), 토큰의 유저가 DB에 없으면 `4401`
(`user_not_found`)로 닫힙니다.

### 연결 직후 자동 동작 (클라이언트 액션 불필요)

서버는 WebSocket 연결이 수락되면 **클라이언트의 `open` 메시지를 기다리지
않고** 곧바로:
1. 새 `EmotionSession`을 생성하고 `open_ok`를 보냅니다.
2. 1~2초(`GREETING_DELAY_MIN_SEC`~`GREETING_DELAY_MAX_SEC`) 랜덤 지연 후,
   서버가 먼저 인사 메시지를 `message_start` → `message` → `message_end`
   순서로 전송합니다. 인사 문구는 `greeting_service.pick_greeting_message`가
   두 후보를 무작위로 뽑아 선택 횟수가 적은 쪽을 고르는 방식(power-of-two-choices)으로
   선택하며, `GreetingMessageStat` 테이블에 선택 횟수를 누적합니다.

---

### 클라이언트 → 서버 메시지

#### `open` — (선택, 이미 자동으로 열려 있으므로 보통 불필요)

이미 세션이 열려 있으면 서버는 기존 `session_id`로 `open_ok`를 다시 보낼
뿐입니다.

```json
{ "type": "open" }
```

#### `message` — 사용자 발화

```json
{ "type": "message", "text": "오늘 정말 힘들었어요" }
```

#### `close` — 세션 종료

```json
{ "type": "close" }
```
→ 확인 절차 없이 바로 세션을 종료하고 `close_ok`를 반환, 분석카드/욕구카드
생성은 트리거하지 않습니다 (분석 트리거는 아래 `[[CONFIRM_CLOSE]]` 자동 감지
경로에서만 일어남 — 명시적 `close`는 세션 정리 종료로만 사용됨).

#### `confirm_close`

레거시 호환용으로 파싱은 되지만, 현재 라우터 로직에서 별도 분기 없이
`close`와 동일하게 취급됩니다.

#### `cancel_close`

```json
{ "type": "cancel_close" }
```
종료 쿨다운 상태로 진입 마커를 남기고 `cancel_close_ok` 확인 메시지를 보냅니다.

#### `task_recommend` — 태스크 추천 수동 요청

```json
{ "type": "task_recommend", "max_items": 5 }
```
대화 중 액티비티 턴이 감지되면 서버가 이미 자동으로 태스크 추천을 실행하므로,
이 메시지는 재요청/수동 트리거용입니다.

#### `ping` — 하트비트

```json
{ "type": "ping" }
```

> 순수 텍스트 프레임(`"ping"`, `"open"`, `"close"`, `"confirm_close"`,
> `"cancel_close"`)도 JSON 없이 그대로 보내면 위와 동일하게 해석됩니다.
> JSON이 아니면서 위 키워드도 아닌 순수 텍스트는 `{"type": "message", "text": "..."}`로
> 처리됩니다.

---

### 서버 → 클라이언트 메시지

#### `open_ok`

```json
{ "type": "open_ok", "session_id": "uuid", "turns": 0 }
```

#### 스트리밍 응답 (오프닝 인사와 사용자 메시지 응답 모두 동일한 포맷)

```json
{ "type": "message_start" }
{ "type": "message_delta", "delta": "안녕하세요," }
{ "type": "message_delta", "delta": " 오늘은 어땠어요..." }
{ "type": "message", "message": "안녕하세요, 오늘은 어땠어요..." }
{ "type": "message_end" }
```

`message_delta`는 60자 단위로 배치되어 전송됩니다. `[[CONFIRM_CLOSE]]` 마커는
스트림에서 제거된 뒤 전송되며, 클라이언트에는 노출되지 않습니다.

#### `close_ok`

```json
{ "type": "close_ok" }
```

#### `analysis_card_ready`

`[[CONFIRM_CLOSE]]` 자동 감지로 세션이 종료됐을 때만 전송됩니다.

```json
{
  "type": "analysis_card_ready",
  "session_id": "uuid",
  "card": {
    "card_id": "uuid",
    "summary": "...",
    "core_emotions": [ { "emotion": "불안", "quote": "...", "reasoning": "..." } ],
    "situation_steps": [ "..." ],
    "risk_flag": false,
    "risk_level": "LOW"
  }
}
```

#### `analysis_card_failed`

```json
{ "type": "analysis_card_failed", "session_id": "uuid", "message": "analysis_card_generation_failed" }
```

욕구카드(need card)는 분석카드 생성 이후 같은 흐름에서 함께 생성되지만,
성공/실패 여부를 알리는 별도의 WS 메시지는 없습니다 (실패 시 서버 로그만
남음). 필요하면 `GET /desire/need-cards/history`로 결과를 확인해야 합니다.

#### `task_recommend_ok`

대화 중 액티비티 턴 직후 자동으로, 또는 `task_recommend` 요청에 대한 응답으로
전송됩니다.

```json
{ "type": "task_recommend_ok", "items": [ { "title": "...", "description": "..." } ] }
```

#### `cancel_close_ok`, `pong`, `error`, `limit`

```json
{ "type": "pong" }
{ "type": "error", "message": "recv_failed" }
{ "type": "limit", "message": "max turns reached" }
```

`error` 메시지 중 `turn_dropped: true`가 포함된 경우는 해당 턴의 LLM 응답이
실패해 저장되지 않았다는 뜻입니다 (`stream_timeout`, `empty_assistant_response` 등).

---

## 4. 분석카드 (`/analyze/api`)

모든 엔드포인트는 `Authorization: Bearer {token}` 필요. 다른 유저 리소스 접근 시 403.

### `POST /analyze/api/sessions`

분석 전용 세션을 생성합니다.

---

### `POST /analyze/api/sessions/{session_id}/cards/auto-from-session`

저장된 EmotionStep transcript로 분석카드를 자동 생성합니다.
**세션 종료 시 서버가 내부적으로 호출하는 핵심 함수와 동일 경로입니다**
(WebSocket `[[CONFIRM_CLOSE]]` 감지 후 자동 호출됨).

**Query:** `?regenerate=true` — 기존 카드가 있으면 삭제 후 재생성

**Request:** body 없음 (또는 `{"title_hint": "선택적 힌트"}`)

**Response:**
```json
{
  "card_id": "uuid",
  "session_id": "uuid",
  "summary": "오늘 직장에서 받은 압박감으로 인해...",
  "core_emotions": [{"emotion": "불안", "quote": "...", "reasoning": "..."}],
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

내용이 비어있는 카드가 생성되면(LLM 실패 등) `502`를 반환합니다.

---

### `POST /analyze/api/sessions/{session_id}/cards/auto`

conversation_log를 직접 보내서 카드를 생성합니다 (DB transcript 불필요).

**Query:** `?regenerate=true`

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

카드를 수동으로 생성합니다 (내부/테스트용). 내용이 비어있으면 `400`.

---

### `GET /analyze/api/sessions/{session_id}/cards`

세션의 분석카드 목록을 조회합니다 (created_at 내림차순). 내용이 비어있는
카드는 필터링되어 응답에 포함되지 않습니다.

---

### `GET /analyze/api/cards/{card_id}`

분석카드 한 건을 조회합니다. 내용이 비어있으면 `404`.

---

### `GET /analyze/api/summaries`

로그인 사용자의 전체 요약(카드) 목록을 조회합니다.

**Query:** `?limit=20&offset=0`

---

### `GET /analyze/api/sessions/{session_id}/summaries`

특정 세션의 요약 목록을 조회합니다.

**Query:** `?limit=20&offset=0`

---

### `PUT /analyze/api/sessions/{session_id}/satisfaction`

세션 만족도(1건)를 생성 또는 갱신합니다(upsert).

**Request:**
```json
{ "rating": 5 }
```

**Response:**
```json
{ "rating_id": "uuid", "session_id": "uuid", "rating": 5, "created_at": "...", "updated_at": "..." }
```

---

### `GET /analyze/api/sessions/{session_id}/satisfaction`

세션 만족도를 조회합니다. 없으면 `404`.

---

## 5. 욕구 분석 (`/desire/need-cards`)

모든 엔드포인트(목록 제외)는 `Authorization: Bearer {token}` 필요.

### `GET /desire/need-cards/list`

8가지 욕구 전체 목록과 메타데이터를 반환합니다 (인증 불필요).

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
    }
  ]
}
```

---

### `POST /desire/need-cards/analyze`

대화 내용에서 8가지 욕구를 분석하고 DB에 저장합니다. `session_id`가 로그인
유저 소유가 아니면 `404`(개인화 힌트가 세션 소유자의 과거 선택 이력을 섞어
넣기 때문에 소유권 확인이 필수).

**Request:**
```json
{ "session_id": "uuid", "conversation_text": "오늘 회사에서 인정받지 못한 것 같아서..." }
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
      "rationale": "...",
      "reflection_message": "...",
      "creature_name_ko": "거북이",
      "creature_emoji": "🐢",
      "creature_description": "오래 사는 존재 — 인내, 지속성, 깊은 방향감"
    }
  ],
  "top4": [...]
}
```

`score`: 0~100. `rank`: 1=가장 높은 욕구, 8=가장 낮은 욕구. `rationale`은
해당 점수의 근거, `reflection_message`는 이 욕구를 선택했을 때 보여줄
개인화된 서술문입니다.

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

---

### `GET /desire/need-cards/history`

로그인 유저의 욕구 분석 히스토리 목록을 반환합니다 (각 항목의 top4만 포함).

**Query:** `?limit=20&offset=0`

**Response:**
```json
{
  "items": [
    { "result_id": "uuid", "session_id": "uuid", "created_at": "2026-01-01T00:00:00", "top4": [...] }
  ],
  "total": 12
}
```

---

### `GET /desire/need-cards/last-selection`

로그인 유저가 마지막으로 선택한 욕구 하나를 반환합니다. 선택 이력이 없으면
`404`.

**Response:** `POST /desire/need-cards/selection`과 동일 형태.

---

### `POST /desire/need-cards/selection`

사용자가 선택한 욕구 **1개**를 `UserNeedSelection`으로 저장하고, 해당 욕구의
UI 렌더링 메타데이터 + 개인화 서술(reflection_message)을 반환합니다.
과거 버전과 달리 리스트가 아닌 단일 코드를 받으며, 이제 DB에 저장됩니다.

**Request:**
```json
{ "selected_need": "Meaning", "session_id": "uuid" }
```

`session_id`는 선택 근거가 된 분석 결과를 정확히 찾기 위한 값으로, 생략하면
유저의 가장 최근 분석 결과로 폴백합니다.

**Response:**
```json
{
  "code": "Meaning",
  "label_ko": "의미",
  "label_en": "Meaning",
  "description": "행동과 노력이 가치 있고 의미 있다고 느끼고 싶음.",
  "icon": "meaning",
  "creature_name_ko": "거북이",
  "creature_emoji": "🐢",
  "creature_description": "오래 사는 존재 — 인내, 지속성, 깊은 방향감",
  "reflection_message": "..."
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
| `GET /health` | 기본 상태 확인 (`app/backend/main.py`) |
| `GET /health/db` | DB 연결 + 필수 테이블 존재 확인 |
| `GET /health/llm` | LLM 응답 확인 (blocking, 5/min 레이트리밋) |
| `GET /health/llm/stream` | LLM 스트리밍 확인 (5/min 레이트리밋) |

---

## 8. GitHub 배포 웹훅 (`/webhook/github`)

### `POST /webhook/github`

GitHub push/PR merge 이벤트를 받아 Render 배포를 트리거하고 Discord로 결과를
알립니다. `main` push → 운영(PROD) 배포, `develop` push → 테스트(TEST) 배포,
`main`으로 merge된 PR → 운영 채널로 커밋 기록 파일 전송. `GITHUB_WEBHOOK_SECRET`이
설정된 경우 `X-Hub-Signature-256` HMAC 서명 검증을 통과해야 처리됩니다. 자세한
환경변수는 `DEPLOYMENT.md` 참조.

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
| `409` | 이미 존재하는 리소스 (예: 세션당 카드 1건 제약 충돌) |
| `422` | Pydantic 유효성 검사 실패 |
| `500` | 서버 내부 오류 |
| `502` | LLM 응답 생성 실패 |
