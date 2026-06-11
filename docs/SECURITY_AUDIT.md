# DeepMe 보안 감사 보고서

> **최초 감사 일자:** 2026-05-04  
> **최종 업데이트:** 2026-05-10 (P0~P3 우선순위 재분류)  
> **Critical 4개:** ✅ 2026-05-09 완료  
> **대상 브랜치:** `main`  
> **감사 범위:** 전체 코드베이스 (`app/`, `alembic/`)

---

## 목차

1. [요약](#요약)
2. [우선순위 기준](#우선순위-기준)
3. [P0 — 긴급 (5개)](#p0--긴급-5개)
4. [P1 — 높음 (6개)](#p1--높음-6개)
5. [P2 — 중간 (8개)](#p2--중간-8개)
6. [P3 — 낮음 (4개)](#p3--낮음-4개)
7. [긍정적 보안 구현](#긍정적-보안-구현)
8. [조치 우선순위 체크리스트](#조치-우선순위-체크리스트)

---

## 요약

| 우선순위 | 건수 | 상태 |
|---------|------|------|
| 🔴 P0 (긴급) | 5 | ⬜ 미진행 |
| 🟠 P1 (높음) | 6 | ⬜ 미진행 |
| 🟡 P2 (중간) | 8 | ⬜ 미진행 |
| 🟢 P3 (낮음) | 4 | ⬜ 미진행 |
| **Critical (해결됨)** | **4** | **✅ 2026-05-09** |
| **합계** | **27** | — |

---

## 우선순위 기준

| 레벨 | 기준 |
|------|------|
| **P0 — 긴급** | 보안 침해 직결. 민감 데이터 유출, 토큰 노출, 정책 조작, API 비용 폭발 위험 높음 |
| **P1 — 높음** | 상당한 공격 위험. CSRF, CORS 우회, 무인증 접근, LLM 파라미터 조작 |
| **P2 — 중간** | 환경·운영 관리 필요. 인증 강화, 필드 제거, 정리 로직, 환경변수 통합 |
| **P3 — 낮음** | 기술부채·모범 사례. 의존성 감사, deprecated 함수, 인코딩, 데모 비활성화 |

---

## P0 — 긴급 (5개)

### P0-1. 사용자 감정 대화 원문이 WARNING 레벨 로그에 노출

**파일:** `app/backend/services/ws_protocol.py:93-99`, `app/backend/routers/emotion_ws.py:345-449`  
**심각도:** H-5  
**영향:** 민감한 심리 데이터가 로그 시스템에 평문 저장

```python
logger.warning(
    "WS RAW EVENT | keys=%s txt=%r bin=%s",
    list(event.keys()),
    (event.get("text") or "")[:80],   # 사용자 원문 WARNING 로그
    bool(event.get("bytes")),
)
# emotion_ws.py에도 임시 디버그 마커들
logger.warning("WS MARK A | before DB fetch")
logger.warning("WS MARK B | after DB fetch, before prompt")
logger.warning("WS MARK C | after prompt load, before stream")
logger.warning("WS PARSED | %s", msg.get("type"))
```

심리 앱 특성상 극도로 민감한 데이터임. WARNING 레벨은 운영 로그 수집기에 무조건 기록됨.

**권장 조치:** `logger.warning` → `logger.debug` 다운그레이드, 임시 디버그 마커 제거

---

### P0-2. WebSocket 토큰을 쿼리 파라미터에서도 수락

**파일:** `app/backend/services/ws_protocol.py:44-49`  
**심각도:** H-4  
**영향:** 토큰이 브라우저 히스토리·프록시 로그에 평문 노출

```python
def extract_token_fallback(websocket: WebSocket) -> str | None:
    for key in ("access_token", "token", "auth_token"):
        if query_params.get(key):
            return query_params.get(key)
```

**권장 조치:** `extract_token_fallback` 함수 제거, Bearer 헤더 또는 HttpOnly 쿠키로만 수락

---

### P0-3. `GET /api/summaries` 무인증 전체 DB 조회

**파일:** `app/analyze/routers/summaries.py:24-35`  
**심각도:** H-8  
**영향:** 모든 사용자의 분석 카드를 무인증으로 열람 가능. `limit=None` 허용으로 전체 반환 가능

```python
@router.get("/summaries", response_model=list[sc.CardOut])
def list_summaries(
    limit: Optional[int] = Query(default=None, gt=0),   # None 허용 → 전체 반환
    offset: Optional[int] = Query(default=None, ge=0),
    db: Session = Depends(get_db),   # 인증 없음
):
```

**권장 조치:** 인증 추가, `limit` 최댓값 강제 (예: 100), 사용자 소유 카드만 반환

---

### P0-4. `/health/llm` 인증 없는 무제한 LLM 호출

**파일:** `app/backend/routers/health_llm.py:19-35`  
**심각도:** H-2  
**영향:** LLM API 비용 폭발, 임의 프롬프트 주입 가능

```python
@router.get("/llm")
def health_llm(q: Optional[str] = Query(None, ...)):
    text = generate_noa_response(
        conversation=[("user", q or DEFAULT_PONG_PROMPT)],
    )
```

`q` 파라미터에 제한이 없고 Rate Limiting도 없어 무제한 LLM 호출 가능.

**권장 조치:** Rate Limiting 적용 또는 인증 요구, `q` 파라미터 길이 제한

---

### P0-5. `EmotionStepCreate.step_type` 검증 없음 — 내부 스텝 타입 주입 가능

**파일:** `app/backend/schemas/emotion.py:35`, `app/backend/routers/emotion.py:99-121`  
**심각도:** M-1  
**영향:** 사용자가 `step_type`에 "activity_suggest", "cancel_close" 등 내부 정책 마커를 직접 주입 가능

```python
class EmotionStepCreate(BaseModel):
    step_type: str   # 검증 없음. 임의 값 허용
```

`POST /emotion/steps`로 `step_type="activity_suggest"` 등 내부 마커를 DB에 주입하면 `is_activity_turn`, `_already_fired` 등 정책 함수의 판단을 오염시킬 수 있음.

**권장 조치:**
```python
from typing import Literal
step_type: Literal["user", "assistant"]   # 허용된 값만 수락
```

---

## P1 — 높음 (6개)

### P1-1. 리프레시 쿠키 `SameSite` 속성 미설정 (CSRF 위험)

**파일:** `app/backend/core/tokens.py:100-108`  
**심각도:** H-1  
**영향:** CSRF 공격으로 리프레시 토큰 포함 요청 제출 가능

```python
response.set_cookie(
    key=REFRESH_COOKIE_NAME,
    value=token,
    httponly=True,
    secure=SECURE_COOKIE,
    path="/",
    # samesite 속성 없음
)
```

**권장 조치:**
```python
response.set_cookie(..., samesite="lax")
```

---

### P1-2. CORS `/prompts` 경로에서 요청 Origin 그대로 반영

**파일:** `app/backend/main.py:47-63`  
**심각도:** H-3  
**영향:** 악의적 웹사이트에서 프롬프트 API 접근 가능

```python
response.headers["Access-Control-Allow-Origin"] = origin or "*"
```

**권장 조치:**
```python
ALLOWED_ORIGINS = set(origins)
if origin in ALLOWED_ORIGINS:
    response.headers["Access-Control-Allow-Origin"] = origin
```

---

### P1-3. CORS `allow_methods=["*"]`, `allow_headers=["*"]`

**파일:** `app/backend/main.py:42-44`  
**심각도:** H-6  
**영향:** TRACE 등 위험 메서드 포함 가능

```python
allow_methods=["*"],   # TRACE 등 위험 메서드 포함 가능
allow_headers=["*"],
```

**권장 조치:**
```python
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
```

---

### P1-4. Desire 서브앱 `POST /need-cards/analyze` 무인증

**파일:** `app/desire/routers/need_card.py:19-24`  
**심각도:** H-7  
**영향:** 무인증으로 LLM 호출 가능, 비용 공격 가능

```python
@router.post("/analyze", response_model=NeedCardResponse)
async def analyze_need_cards(
    payload: NeedCardRequest,   # 인증 없음
    db: Session = Depends(get_session),
) -> NeedCardResponse:
```

`conversation_text` 필드에 크기 제한이 없어 대용량 텍스트를 LLM에 전송해 토큰 비용을 유발할 수 있음.

**권장 조치:** 인증 추가, `conversation_text` 최대 길이 제한 (예: 20,000자)

---

### P1-5. `POST /emotion/steps/generate` — 사용자 제공 temperature/max_tokens 검증 없이 LLM 전달

**파일:** `app/backend/routers/emotion.py:124-204`, `app/backend/schemas/emotion.py:55-64`  
**심각도:** H-9  
**영향:** 사용자가 `temperature`, `max_completion_tokens` 조작으로 과도한 LLM 비용 유발 가능

```python
class EmotionStepGenerateInput(BaseModel):
    temperature: Optional[float] = 0.72         # 범위 검증 없음
    max_completion_tokens: Optional[int] = 500  # 상한 없음

# emotion.py에서 그대로 LLM에 전달
response = generate_noa_response(
    temperature=input_data.temperature,          # 사용자 제공값
    max_tokens=input_data.max_completion_tokens, # 사용자 제공값
)
```

`temperature=-1` 또는 `max_completion_tokens=100000` 등의 값 전달 시 LLM API 오류 또는 과도한 비용 발생.

**권장 조치:**
```python
from pydantic import Field
temperature: Optional[float] = Field(default=0.72, ge=0.0, le=2.0)
max_completion_tokens: Optional[int] = Field(default=500, ge=1, le=2000)
```

---

### P1-6. `NeedCardRequest.conversation_text` 크기 제한 없음

**파일:** `app/desire/schemas/need_card.py:9-13`  
**심각도:** M-10  
**영향:** 수십만 자 텍스트 전송으로 LLM 토큰 비용 폭발 가능

```python
class NeedCardRequest(BaseModel):
    conversation_text: str   # 길이 제한 없음
```

**권장 조치:**
```python
conversation_text: str = Field(..., max_length=20000)
```

---

## P2 — 중간 (8개)

### P2-1. `EmotionStepGenerateInput.system_prompt` 필드 제거

**파일:** `app/backend/schemas/emotion.py:63`  
**심각도:** M-2  
**영향:** 스키마에 존재하면 혼선을 줄 수 있음

**상황:** `emotion.py:144`에서 `input_data.system_prompt`를 사용하지 않고 `get_system_prompt()`를 호출하므로 실제 인젝션 경로는 아님.

**권장 조치:** `system_prompt` 필드 스키마에서 제거

---

### P2-2. `logout` 엔드포인트 인증 처리 강화

**파일:** `app/backend/routers/auth.py:29-32, 307-332`  
**심각도:** M-3  
**영향:** `get_current_user` import 실패 시 인증 없이 호출 가능, RT DB 무효화 skip

```python
try:
    from app.backend.dependencies.auth import get_current_user
except Exception:
    get_current_user = None   # import 실패 시 None 설정
```

**권장 조치:** import 실패 시 앱 시작 자체를 실패시킬 것

---

### P2-3. `EMOTION_NO_AUTH_WEB_TEST` 경고 추가 및 프로덕션 가드

**파일:** `app/backend/services/web_test_user.py:38-40`  
**심각도:** M-4  
**영향:** 환경변수 실수 설정 시 WebSocket 인증 전체 우회

```python
allow_web_test = os.getenv("EMOTION_NO_AUTH_WEB_TEST", "false").lower() == "true"
if allow_web_test:
    return ensure_web_test_user(db)   # 인증 없이 통과
```

**권장 조치:** `true`일 때 시작 시 명시적 경고, `APP_ENV=production`에서 강제 무시

---

### P2-4. `TaskRecommendRequest.max_items` 상한선 추가

**파일:** `app/backend/schemas/emotion.py:97`  
**심각도:** M-6

```python
max_items: Optional[int] = 5   # 상한선 없음
```

**권장 조치:**
```python
max_items: Optional[int] = Field(default=5, ge=1, le=20)
```

---

### P2-5. 만료된 RefreshToken 정기 정리 로직 추가

**파일:** `app/backend/models/refresh_token.py`  
**심각도:** M-7  
**영향:** 로그인마다 RT 레코드가 쌓여 DB 비대화 및 쿼리 성능 저하

만료/폐기된 RT 레코드를 정기적으로 삭제하는 로직이 없음.

**권장 조치:** 로그인·리프레시 시 만료 RT 정리 또는 주기적 배치 정리

---

### P2-6. `dependencies/auth.py` 에러 메시지 인코딩 수정

**파일:** `app/backend/dependencies/auth.py:20, 26`  
**심각도:** M-8

```python
raise HTTPException(status_code=401, detail="?¸ì¦ ?•ë³´ê°€ ?†ìŠµ?ˆë‹¤")
```

파일 인코딩 문제로 한글이 깨져 클라이언트에 비정상 문자열 전달.

**권장 조치:** 파일을 UTF-8로 재저장하거나 ASCII 안전한 영문 메시지로 교체

---

### P2-7. LLM 모델명 화이트리스트 구현

**파일:** `app/core/llm_settings.py:78-83`  
**심각도:** M-9  
**영향:** 존재하지 않는 모델명 전달 시 런타임 오류

```python
model=_read_first(model_names, model_default),   # 검증 없이 그대로 사용
```

**권장 조치:**
```python
ALLOWED_MODELS = {"gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet-20241022"}
if model not in ALLOWED_MODELS:
    raise ValueError(f"허용되지 않은 모델: {model}")
```

---

### P2-8. 쿠키 보안 환경변수 통합 정리

**파일:** `app/backend/routers/auth.py:46`, `app/backend/core/tokens.py:30`  
**심각도:** M-11  
**영향:** 유사한 역할의 환경변수 `COOKIE_SECURE` / `SECURE_COOKIE` 혼재, 기본값도 상이

**권장 조치:** 단일 환경변수로 통합, 프로덕션 배포 검증 스크립트에서 확인

---

## P3 — 낮음 (4개)

### P3-1. 의존성 정기 보안 감사 CI 파이프라인 통합

**파일:** `requirements.txt`  
**심각도:** L-1  
**영향:** 향후 발견되는 CVE에 늦게 대응

`python-jose 3.5.0`은 `PyJWT`에 비해 유지보수가 덜 활발함.

**권장 조치:**
```bash
pip install pip-audit
pip-audit   # 월 1회 실행 권장
```

---

### P3-2. `datetime.utcnow()` deprecated 교체

**파일:** `app/backend/models/refresh_token.py:21`, `app/backend/services/auth_service.py:68`, `app/backend/services/ws_session_service.py:32`, `app/backend/routers/emotion.py:115` 등  
**심각도:** L-2  
**영향:** Python 3.12에서 deprecation 경고 (보안 직접 영향 없음)

```python
default_factory=datetime.utcnow   # deprecated
```

**권장 조치:**
```python
from datetime import datetime, timezone
default_factory=lambda: datetime.now(timezone.utc)
```

---

### P3-3. User-Agent 저장 시 길이 제한 추가

**파일:** `app/backend/routers/auth.py:244-246`  
**심각도:** L-3  
**영향:** 조작된 User-Agent가 DB에 저장됨 (로그 포이즈닝)

```python
user_agent=request.headers.get("user-agent"),   # 검증 없이 저장
```

**권장 조치:** User-Agent 길이 제한 (512자), X-Forwarded-For 헤더 신뢰 여부 명시

---

### P3-4. Demo 라우터 프로덕션 비활성화

**파일:** `app/backend/routers/demo.py`  
**심각도:** L-4  
**영향:** 개발용 데모 UI가 운영에서도 접근 가능

`/demo/emotion-analysis` 경로가 환경 구분 없이 항상 활성화됨.

**권장 조치:** `APP_ENV=production`일 때 demo 라우터 비활성화

---

## P2 추가 항목

### P2-9. Rate Limiting 구현

**파일:** 전체 프로젝트  
**심각도:** M-5  
**영향:** 브루트 포스 로그인, DDoS, LLM API 비용 공격

**권장 조치:**
```bash
pip install slowapi
```
```python
@limiter.limit("5/minute")
def login_for_access_token(...):
```

---

## 긍정적 보안 구현

감사 과정에서 잘 구현된 보안 패턴도 확인됨.

| 항목 | 파일 | 설명 |
|------|------|------|
| **RT 재사용 탐지** | `auth_service.py:65-71` | 재사용 시 해당 사용자의 모든 RT 즉시 무효화 |
| **RT 해시 저장** | `auth_service.py:74` | DB에 RT 원문 대신 SHA-256 해시만 저장 |
| **JWT 타입 검증** | `tokens.py:66-70` | `typ` 클레임으로 access/refresh 혼용 방지 |
| **WebSocket 입력 크기 제한** | `emotion_ws.py:409` | 8KB 제한 적용 |
| **`LeakGuard` 유출 탐지** | `ws_utils.py:43-86` | 시스템 프롬프트 유출 탐지 레이어 |
| **DB URL 마스킹** | `db/session.py:22-29` | 로그에 DB 비밀번호 마스킹 처리 |
| **ORM 전용 DB 접근** | 전체 | SQLModel/SQLAlchemy ORM만 사용, 원시 SQL 최소화 |
| **`.env` gitignore** | `.gitignore` | 환경 파일 버전 관리 제외 확인 |
| **RT TTL 및 만료 관리** | `tokens.py:79-83` | Refresh Token 명시적 만료 시간 설정 |
| **SSL 자동 적용** | `db/session.py:48-50` | Render/Neon 환경에서 `sslmode=require` 자동 추가 |
| **LLM JSON 스키마 검증** | `llm_card.py`, `need_analyzer.py` | LLM 출력 Pydantic 검증 및 허용 목록 기반 감정 검증 |
| **페이지네이션 상한** | `emotion.py:45-46` | `limit: int = Query(20, ge=1, le=100)` — 최대 100 제한 |
| **세션 소유권 검증** | `emotion.py:66-68, 105-107` | 스텝 조회 시 `sess.user_id != emotion_user_id` 검사 |

---

## 조치 우선순위 체크리스트

### 💚 Critical — 완료 (2026-05-09)

- [x] **C-1** `PUT /prompts/system`, `PUT /prompts/task` API 전체 삭제
- [x] **C-2** JWT 기본값 하드코딩 제거, 환경변수 강제 설정
- [x] **C-3** `FAKE_USERS_DB` 및 `/auth/token` 엔드포인트 삭제
- [x] **C-4** `analyze/routers/cards.py` 모든 엔드포인트 인증 추가 및 소유권 검증

### 🔴 P0 — 긴급 (즉시 처리)

- [ ] **P0-1** `ws_protocol.py` 사용자 원문 로깅을 DEBUG 레벨로 다운그레이드, `emotion_ws.py` 임시 디버그 마커 제거
- [ ] **P0-2** WebSocket `extract_token_fallback` 함수 제거, Bearer 헤더·HttpOnly 쿠키만 수락
- [ ] **P0-3** `GET /api/summaries` 인증 추가, `limit` 최댓값 강제 (100), 사용자 카드만 반환
- [ ] **P0-4** `/health/llm` Rate Limiting 추가 또는 인증 요구, `q` 파라미터 길이 제한
- [ ] **P0-5** `EmotionStepCreate.step_type`을 `Literal["user", "assistant"]`로 제한

### 🟠 P1 — 높음 (다음 릴리즈 전)

- [ ] **P1-1** `set_refresh_cookie()`에 `samesite="lax"` 추가
- [ ] **P1-2** CORS `/prompts` Origin 검증을 화이트리스트 기반으로 수정
- [ ] **P1-3** CORS `allow_methods`, `allow_headers` 명시적 목록으로 변경
- [ ] **P1-4** `POST /need-cards/analyze` 인증 추가, `conversation_text` 최대 길이 제한 (20,000자)
- [ ] **P1-5** `EmotionStepGenerateInput`에 `temperature` (0.0~2.0), `max_completion_tokens` (1~2000) 범위 검증 추가
- [ ] **P1-6** `NeedCardRequest.conversation_text` 최대 길이 제한 (20,000자)

### 🟡 P2 — 중간 (1개월 내)

- [ ] **P2-1** `EmotionStepGenerateInput`에서 `system_prompt` 필드 제거
- [ ] **P2-2** `logout` 엔드포인트 인증 처리 강화 및 RT DB 무효화 보장
- [ ] **P2-3** `EMOTION_NO_AUTH_WEB_TEST=true` 시 경고 로그 및 프로덕션 강제 무시
- [ ] **P2-4** `TaskRecommendRequest.max_items`에 범위 제한 (1~20) 추가
- [ ] **P2-5** 만료 RefreshToken 정기 정리 로직 추가 (로그인·리프레시 시 또는 배치)
- [ ] **P2-6** `dependencies/auth.py` 인코딩 수정 및 한글 에러 메시지 복구
- [ ] **P2-7** LLM 모델명 화이트리스트 구현 (gpt-4o, gpt-4o-mini, claude-3-5-sonnet)
- [ ] **P2-8** 쿠키 보안 환경변수 (`COOKIE_SECURE` / `SECURE_COOKIE`) 통합 정리
- [ ] **P2-9** `slowapi`로 주요 엔드포인트 Rate Limiting 구현 (로그인 5/min 등)

### 🟢 P3 — 낮음 (분기 단위)

- [ ] **P3-1** `pip-audit` CI 파이프라인 통합 (월 1회 자동 실행)
- [ ] **P3-2** `datetime.utcnow()` → `datetime.now(timezone.utc)` 전체 교체
- [ ] **P3-3** User-Agent 저장 시 길이 제한 (512자) 추가
- [ ] **P3-4** Demo 라우터 (`/demo/*`) `APP_ENV=production`일 때 비활성화

---

*이 문서는 코드 정적 분석 기반으로 작성됨. 실제 운영 환경의 방화벽, TLS, 인프라 설정은 별도 점검 필요.*
