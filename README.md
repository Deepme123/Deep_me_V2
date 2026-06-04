# Deep_me_V2

사용자의 감정 대화를 실시간으로 분석하여 심리 인사이트 카드를 생성하고, 욕구/필요(Need) 분석까지 제공하는 AI 감정 상담 플랫폼입니다.

## 핵심 기능

- **감정 대화**: WebSocket 기반 실시간 LLM 스트리밍 대화
- **분석카드 생성**: 대화 종료 후 자동으로 심리 인사이트 카드 생성
- **욕구/필요 분석**: 8가지 심리경제학적 욕구 분석 및 우선순위 도출
- **태스크 추천**: 감정 세션 후 실천 가능한 행동 과제 추천
- **위험 감지**: 자해/자살 의향 등 위험 키워드 자동 플래그 처리

## 기술 스택

| 항목 | 사항 |
|------|------|
| **Backend** | Python 3.10+ FastAPI + SQLModel + PostgreSQL + Alembic |
| **LLM** | OpenAI (gpt-4o-mini 기본) / Anthropic Claude (전환 가능) |
| **Auth** | Google OAuth 2.0 + JWT (Access/Refresh Token 이중 구조) |
| **Frontend** | React 19 + TypeScript + Vite + React Router v7 |
| **Deploy** | Render (Web Service + PostgreSQL) |

## 서비스 구조

이 프로젝트는 **Python 모노레포** 내 여러 FastAPI 서브앱으로 구성됩니다.

- `app/backend`: 인증, 감정대화, 태스크 API, WebSocket
- `app/analyze`: 분석카드 자동 생성, 요약
- `app/desire`: 8가지 욕구 분석 및 우선순위 도출

모두 단일 Uvicorn 프로세스(`app.main:app`)에서 실행됩니다.

## 프로젝트 구조

```
Deep_me_V2/
├── app/                    # Python 백엔드
│   ├── main.py             # 전체 서비스 마운트 진입점
│   ├── backend/            # 인증, 감정대화, 태스크 API
│   ├── analyze/            # 분석카드 생성 서비스
│   ├── desire/             # 욕구/필요 분석 서비스
│   ├── core/               # LLM 추상화, 공통 설정
│   └── db/                 # DB 세션 관리
├── frontend/               # React 프론트엔드
│   ├── apps/beta/          # 일반 사용자 UI
│   ├── apps/admin/         # 관리자 모니터링 UI
│   └── shared/             # 공유 타입, 클라이언트
├── alembic/                # DB 마이그레이션
├── tests/                  # 테스트 모음
└── docs/                   # 문서 (인수인계 포함)
```

상세한 설명은 [docs/handover/ARCHITECTURE.md](docs/handover/ARCHITECTURE.md)를 참조하세요.

## 요구 사항

- Python 3.11 이상
- pip
- 루트 `.env` 파일

Python 의존성은 `requirements.txt` 에 정리되어 있습니다.

## 설치 및 실행

### 1단계: 환경 준비

```bash
# Python 가상환경 생성
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2단계: 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일에서 최소한 다음을 설정하세요:
```env
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/deepme
JWT_SECRET_KEY=your-strong-secret-key
```

### 3단계: 데이터베이스

```bash
# DB 마이그레이션 (새로운 DB)
alembic upgrade head

# 기존 운영 DB 연동 시
alembic stamp 0001_base_schema
alembic upgrade head
```

자세한 가이드는 [docs/handover/DEVELOPMENT_GUIDE.md](docs/handover/DEVELOPMENT_GUIDE.md)를 참조하세요.

## 로컬 실행

백엔드 서버는 프로젝트 루트에서:

```bash
uvicorn app.main:app --reload
```

### 주요 접속 경로

| URL | 설명 |
|-----|------|
| `http://localhost:8000/health` | API 헬스체크 |
| `http://localhost:8000/health/db` | DB 연결 확인 |
| `http://localhost:8000/health/llm` | LLM 연결 확인 |
| `http://localhost:8000/demo/emotion-analysis` | QA 테스트 UI (HTML) |
| `http://localhost:8000/docs` | Swagger UI |
| `WS ws://localhost:8000/ws/emotion` | WebSocket 대화 채널 |

프론트엔드 (별도 터미널):

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

## 마이그레이션

현재 마이그레이션 상태 확인:

```bash
alembic current    # 현재 적용 버전
alembic history    # 전체 이력
```

**최신 마이그레이션** (`0005_behavior_patterns`):
- `core_emotions` 배열에 `quote`, `reasoning` 필드 추가
- `situation` VARCHAR → `situation_steps` JSONB (1~4단계)
- `behavior_patterns` JSONB 컬럼 추가

롤백:

```bash
alembic downgrade -1        # 한 단계 롤백
alembic downgrade base      # 전체 초기화
```

자세한 DB 스키마는 [docs/handover/DATABASE.md](docs/handover/DATABASE.md)를 참조하세요.

## 테스트

전체 테스트:

```bash
pytest
```

특정 모듈별:

```bash
pytest tests/backend/              # 백엔드 전체
pytest tests/analyze/              # 분석 서비스
pytest tests/desire/               # 욕구분석 서비스
pytest tests/core/                 # LLM 코어
```

특정 파일:

```bash
pytest tests/backend/test_demo_router.py -v
```

커버리지:

```bash
pytest --cov=app --cov-report=term-missing
```

## 배포

현재 **Render** 플랫폼 사용:

| 항목 | 값 |
|------|-----|
| 실행 명령 | `uvicorn app.main:app` |
| 사전 배포 | `alembic upgrade head` |
| DB | Render PostgreSQL (또는 Neon) |

전체 환경변수 목록과 배포 절차는 [docs/handover/DEPLOYMENT.md](docs/handover/DEPLOYMENT.md)를 참조하세요.

## 문서

- [docs/handover/HANDOVER.md](docs/handover/HANDOVER.md) — 인수인계 가이드 및 체크리스트
- [docs/handover/ARCHITECTURE.md](docs/handover/ARCHITECTURE.md) — 시스템 아키텍처
- [docs/handover/API.md](docs/handover/API.md) — API 레퍼런스
- [docs/handover/DATABASE.md](docs/handover/DATABASE.md) — 데이터베이스 스키마
- [docs/handover/DEPLOYMENT.md](docs/handover/DEPLOYMENT.md) — 배포 및 환경 설정
- [docs/handover/DEVELOPMENT_GUIDE.md](docs/handover/DEVELOPMENT_GUIDE.md) — 로컬 개발 가이드
- [docs/handover/FRONTEND.md](docs/handover/FRONTEND.md) — 프론트엔드 구조

## 중요 사항

1. **`[[CONFIRM_CLOSE]]` 마커**: 대화 자동 종료는 이 문자열이 모델 응답 끝에 있을 때만 트리거됩니다.
2. **JWT_SECRET_KEY 필수**: 운영 환경에서는 반드시 강력한 랜덤 키로 설정하세요.
3. **LLM 프로바이더**: `LLM_PROVIDER=anthropic` 으로 OpenAI/Claude 전환 가능.
4. **리프레시 토큰 재사용**: 탈취된 토큰 재사용 시 해당 유저의 모든 세션이 무효화됩니다.
