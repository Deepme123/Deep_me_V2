# 로컬 개발 가이드

---

## 1. 사전 요구사항

| 항목 | 버전 |
|------|------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |
| PostgreSQL | 14+ |

---

## 2. 최초 세팅

### 2.1 저장소 클론

```bash
git clone <repo-url>
cd Deep_me_V2
```

### 2.2 Python 가상환경

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2.3 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일에서 최소한 아래 항목을 채워야 합니다:

```env
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/deepme

# 로컬 개발 시 쿠키 설정
SECURE_COOKIE=false
```

### 2.4 DB 생성 및 마이그레이션

```bash
# PostgreSQL에서 DB 생성 (psql 또는 PgAdmin)
createdb deepme

# 마이그레이션 적용
alembic upgrade head
```

### 2.5 백엔드 실행

```bash
uvicorn app.main:app --reload
# → http://localhost:8000
```

### 2.6 프론트엔드 실행

```bash
cd frontend
npm install
cp .env.example .env      # 프론트엔드 환경변수
npm run dev
# → http://localhost:5173
```

---

## 3. 주요 접속 URL

| URL | 설명 |
|-----|------|
| `http://localhost:8000/health` | API 서버 헬스체크 |
| `http://localhost:8000/health/db` | DB 연결 확인 |
| `http://localhost:8000/health/llm` | LLM 연결 확인 |
| `http://localhost:8000/demo/emotion-analysis` | QA 테스트 UI |
| `http://localhost:8000/docs` | FastAPI 자동 생성 Swagger UI |
| `http://localhost:8000/redoc` | ReDoc API 문서 |
| `http://localhost:5173/beta/chat` | React 프론트엔드 |

---

## 4. 테스트 실행

### 전체 테스트

```bash
pytest
```

### 특정 모듈 테스트

```bash
pytest tests/backend/              # 백엔드 전체
pytest tests/analyze/              # 분석 서비스
pytest tests/desire/               # 욕구분석 서비스
pytest tests/core/                 # LLM 코어
```

### 특정 파일

```bash
pytest tests/backend/test_demo_router.py -v
```

### 커버리지

```bash
pytest --cov=app --cov-report=term-missing
```

---

## 5. 테스트 파일 목록

```
tests/
├── backend/
│   ├── test_demo_router.py              # QA Demo 라우터
│   ├── test_emotion_ws_analysis_trigger.py  # WS 분석 트리거
│   ├── test_emotion_ws_auth.py          # WS 인증
│   ├── test_emotion_ws_close_flow.py    # WS 종료 흐름
│   ├── test_health_llm.py              # LLM 헬스체크
│   ├── test_llm_service.py             # LLM 서비스
│   ├── test_prompt_loader.py           # 프롬프트 로더
│   ├── test_stream_bridge.py           # 스트리밍 브리지
│   └── test_task_llm_service.py        # 태스크 추천 서비스
├── analyze/
│   ├── test_cards_from_session.py      # 세션 기반 카드 생성
│   ├── test_llm_card.py                # LLM 카드 생성
│   └── test_schema_migrations.py       # 스키마 마이그레이션
├── desire/
│   └── test_need_analyzer.py           # 욕구분석
└── core/
    ├── test_import_smoke.py            # 임포트 스모크 테스트
    ├── test_llm_factory.py             # LLM 팩토리
    ├── test_anthropic_provider.py      # Anthropic 프로바이더
    ├── test_openai_provider.py         # OpenAI 프로바이더
    └── test_provider_contracts.py      # 프로바이더 인터페이스 계약
```

---

## 6. DB 마이그레이션 작업

### 새 마이그레이션 생성

```bash
alembic revision --autogenerate -m "add_new_column"
# alembic/versions/ 에 새 파일 생성됨
# 생성된 파일 검토 후 커밋
```

### 마이그레이션 상태 확인

```bash
alembic current      # 현재 적용된 버전
alembic history      # 전체 마이그레이션 이력
```

**현재 마이그레이션 버전:**
- `0005_behavior_patterns` (최신, 2026-05-05)
  - `core_emotions` 배열에 `quote`, `reasoning` 필드 추가
  - `situation` VARCHAR → `situation_steps` JSONB 변경 (1~4단계)
  - `behavior_patterns` JSONB 컬럼 추가
  - 욕구 카드 DB 연동 완료 (`need_card_result`, `need_card_score` 테이블)

### 롤백

```bash
alembic downgrade -1        # 한 단계 롤백
alembic downgrade base      # 전체 초기화
```

---

## 7. 보안 설정

**JWT_SECRET_KEY 필수:**
로컬 개발 환경에서도 `.env`에 반드시 설정해야 합니다.

```env
# 로컬 개발용 (임의 값)
JWT_SECRET_KEY=dev_secret_key_for_local_testing
JWT_REFRESH_SECRET=dev_refresh_secret_for_local_testing
```

---

## 8. LLM 설정 변경

`.env`에서 변경 후 서버 재시작만 하면 됩니다.

```env
# Anthropic으로 전환
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-3-5-sonnet-20241022

# 또는 OpenAI 유지, 모델만 변경
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
```

LLM 정상 동작 확인:
```bash
curl http://localhost:8000/health/llm
```

---

## 9. 자주 발생하는 문제

### PostgreSQL 연결 실패

```
sqlalchemy.exc.OperationalError: could not connect to server
```
→ PostgreSQL 서비스 실행 중인지 확인: `pg_isready`  
→ `DATABASE_URL` 환경변수 값 확인  
→ DB 이름과 사용자 권한 확인

---

### 마이그레이션 충돌

```
sqlalchemy.exc.ProgrammingError: table "user" already exists
```
→ 이미 테이블이 있는 DB에 `upgrade head`를 실행한 경우  
→ 해결: `alembic stamp <version>` 후 `alembic upgrade head`

---

### JWT 쿠키 미설정

```
401 Unauthorized (리프레시 토큰 없음)
```
→ `SECURE_COOKIE=false` 확인 (로컬 HTTP 환경에서 필수)

---

### CORS 오류

```
Access-Control-Allow-Origin 헤더 없음
```
→ `CORS_ALLOW_ORIGINS`에 프론트엔드 주소 추가 (`http://localhost:5173`)

---

### `[[CONFIRM_CLOSE]]` 미발생

→ 자동 종료가 안 된다면 시스템 프롬프트에 해당 마커 출력 조건이 포함되어 있는지 확인  
→ `app/backend/resources/system_prompt.txt` 파일에서 현재 프롬프트 직접 확인  
→ 대화 턴 수(`SESSION_MAX_TURNS`) 초과 여부 확인

### JWT_SECRET_KEY 미설정 오류

```
ValueError: JWT_SECRET_KEY is required
```

→ `.env` 파일에 `JWT_SECRET_KEY` 값 설정 (로컬은 임의 값 OK, 운영은 강력한 키 필수)

---

## 10. 브랜치 전략

```
main          # 운영 브랜치 (직접 커밋 금지)
develop       # 통합 브랜치
feat/*        # 기능 개발
fix/*         # 버그 수정
hotfix/*      # 운영 긴급 수정
```

PR은 `main`으로 머지 전 리뷰 필수.
