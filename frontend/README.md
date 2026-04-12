# Frontend 작업 공간

이 디렉터리는 제품용 웹 UI를 위한 프론트엔드 작업 공간입니다.

현재 원칙은 다음과 같습니다.

- 내부 QA 데모는 기존 HTML 화면을 유지한다.
- 일반 베타 사용자 화면은 React로 만든다.
- 운영자 및 마스터 모니터링 화면도 React로 만든다.

즉, 이 디렉터리는 `/beta/*` 와 `/admin/*` 화면을 위한 작업 공간입니다.

## 현재 구조

- `apps/beta`: 일반 베타 사용자용 화면
- `apps/admin`: 운영자 및 마스터용 화면
- `shared`: 공통 타입, API, WebSocket, 유틸리티
- `src`: React 엔트리, 라우터, 전역 스타일

## 실행 전 준비

현재 프론트엔드는 Vite + React + TypeScript 기준으로 구성되어 있습니다.

필요한 것:

- Node.js
- npm

루트 프로젝트와 별도로, 이 디렉터리 안에서 프론트엔드 의존성을 설치해야 합니다.

```bash
cd frontend
npm install
```

## 환경 변수

`.env.example` 을 참고해서 `frontend/.env` 파일을 만들 수 있습니다.

기본값 예시:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

별도 설정이 없으면 프론트엔드는 로컬 백엔드 `8000` 포트를 기준으로 API와 WebSocket에 연결합니다.

## 개발 실행

백엔드는 프로젝트 루트에서 실행합니다.

```bash
uvicorn app.main:app --reload
```

프론트는 `frontend/` 안에서 실행합니다.

```bash
npm run dev
```

기본 개발 서버 주소는 다음입니다.

- 프론트: `http://localhost:5173`
- 백엔드: `http://localhost:8000`

## 빌드

```bash
npm run build
```

미리보기:

```bash
npm run preview
```

## 현재 라우트 골격

현재 React 쪽에는 다음 경로 골격이 준비되어 있습니다.

- `/beta`
- `/beta/chat`
- `/beta/result/:sessionId`
- `/admin`
- `/admin/sessions`
- `/admin/sessions/:sessionId`

## QA 데모와의 관계

기존 QA 데모는 FastAPI가 직접 서빙합니다.

- 경로: `/demo/emotion-analysis`
- 위치: `app/backend/demo_ui/`

이 화면은 대화 흐름, 종료 흐름, 분석 카드 회귀 테스트를 위한 기준 화면으로 유지합니다.
React 화면은 제품용 사용자 경험과 운영 화면을 확장하기 위한 별도 작업입니다.
