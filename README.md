# Deep_me_V2

DeepMe 대화, 욕구 분석, 분석 카드 생성을 위한 FastAPI 기반 백엔드 프로젝트입니다.

현재 저장소에는 다음이 포함되어 있습니다.

- 통합 FastAPI 엔트리포인트 `app.main`
- 감정 대화 API 및 WebSocket 흐름
- 분석 카드와 요약 관련 백엔드 패키지
- FastAPI가 직접 서빙하는 내부 QA용 데모 UI
- 앞으로 공개 베타 UI와 관리자 UI가 들어갈 `frontend/` 작업 공간

## 현재 구성

백엔드는 크게 세 영역으로 나뉩니다.

- `app/backend`: 핵심 API, 인증, WebSocket, 작업 추천, QA 데모 라우팅
- `app/analyze`: 분석 카드와 요약 관련 서비스
- `app/desire`: 욕구 및 니즈 분석 서비스

기존 HTML WebSocket 데모는 `/demo/emotion-analysis` 에서 계속 사용할 수 있습니다.
이 화면은 대화 흐름과 분석 카드 회귀 테스트를 위해 유지되며, 제품용 웹 UI는
`frontend/` 아래에서 별도로 확장할 수 있게 분리해 두었습니다.

## 프로젝트 구조

```text
Deep_me_V2/
  app/
    backend/
      demo_ui/
      resources/
    analyze/
    desire/
  frontend/
    apps/
      beta/
      admin/
    shared/
  tests/
  docs/
```

구조에 대한 자세한 설명은 [docs/repo-structure.md](docs/repo-structure.md)에서 볼 수 있습니다.

## 요구 사항

- Python 3.11 이상
- pip
- 루트 `.env` 파일

Python 의존성은 `requirements.txt` 에 정리되어 있습니다.

## 설치

```bash
pip install -r requirements.txt
```

`.env.example` 을 참고해서 프로젝트 루트에 `.env` 파일을 만들고, 데이터베이스와
LLM 관련 환경 변수를 설정한 뒤 실행하세요.

## 실행

반드시 프로젝트 루트에서 실행합니다.

```bash
uvicorn app.main:app --reload
```

또는:

```bash
python -m app.main
```

자주 확인하는 경로:

- `GET /health`
- `GET /health/db`
- `GET /demo/emotion-analysis`
- `WS /ws/emotion`

## 데이터베이스 마이그레이션

이 프로젝트는 Alembic을 사용합니다.

새 데이터베이스라면:

```bash
alembic upgrade head
```

기존 운영 데이터베이스를 연결할 때는 `RUN.md`에 적힌 대로 먼저 base revision을
stamp 한 뒤 업그레이드합니다.

```bash
alembic stamp 0001_base_schema
alembic upgrade head
```

## 테스트

전체 테스트 실행:

```bash
pytest
```

QA 데모 라우터 테스트만 실행:

```bash
pytest tests/backend/test_demo_router.py -q
```

## 프론트엔드 구조 메모

`frontend/` 는 앞으로 제품용 웹 UI를 담을 별도 경계입니다.

- `frontend/apps/beta`: 일반 베타 테스터용 UI
- `frontend/apps/admin`: 운영자 및 마스터 모니터링 UI
- `frontend/shared`: 공통 프론트엔드 코드

현재 내부 QA 데모는 여전히 FastAPI가 직접 서빙하며, React 앱으로 교체된 상태는 아닙니다.

## 배포 메모

현재 Render 기준 백엔드 시작 명령은 다음을 유지하면 됩니다.

```bash
uvicorn app.main:app
```

웹 프로세스 시작 전에 마이그레이션을 먼저 실행합니다.

```bash
alembic upgrade head
```
