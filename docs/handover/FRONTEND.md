# 프론트엔드

> 현재 상태: 라우트 뼈대 + 공유 인프라 완성, 각 페이지 기능 구현 진행 중

---

## 1. 기술 스택

| 항목 | 버전 |
|------|------|
| React | 19.0 |
| TypeScript | 5.0 |
| Vite | 8.0 |
| React Router | 7.0 |
| 빌드 | npm |

---

## 2. 디렉토리 구조

```
frontend/
├── src/
│   ├── main.tsx          # React 앱 진입점
│   ├── App.tsx           # 루트 컴포넌트
│   ├── router.tsx        # 전체 라우트 정의
│   └── styles.css        # 전역 스타일
│
├── apps/
│   ├── beta/                        # 일반 사용자 UI
│   │   ├── BetaLayout.tsx           # 레이아웃 공통 래퍼
│   │   ├── pages/
│   │   │   ├── Home.tsx             # 랜딩/시작 화면
│   │   │   ├── Chat.tsx             # 감정 대화 화면 (WebSocket)
│   │   │   └── Result.tsx           # 분석카드 결과 화면
│   │   └── README.md
│   │
│   └── admin/                       # 관리자/운영자 UI
│       ├── AdminLayout.tsx          # 레이아웃 래퍼
│       ├── pages/
│       │   ├── SessionList.tsx      # 세션 목록
│       │   └── SessionDetail.tsx    # 세션 상세
│       └── README.md
│
├── shared/                          # 앱 간 공유 코드
│   ├── api/                         # REST API 클라이언트 함수
│   ├── config/                      # baseURL 등 설정
│   ├── types/                       # 공유 TypeScript 타입
│   └── ws/                          # WebSocket 클라이언트
│
├── package.json
├── vite.config.ts
├── tsconfig.json
└── .env.example
```

---

## 3. 라우트 구조

| 경로 | 컴포넌트 | 설명 |
|------|---------|------|
| `/beta` | `BetaLayout` → `Home` | 일반 사용자 랜딩 |
| `/beta/chat` | `BetaLayout` → `Chat` | 감정 대화 (WebSocket 연결) |
| `/beta/result/:sessionId` | `BetaLayout` → `Result` | 분석카드 결과 |
| `/admin` | `AdminLayout` → `SessionList` | 관리자 랜딩 |
| `/admin/sessions` | `AdminLayout` → `SessionList` | 세션 목록 |
| `/admin/sessions/:sessionId` | `AdminLayout` → `SessionDetail` | 세션 상세 |

---

## 4. 환경변수

`frontend/.env` 파일 (`.env.example` 참고):

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

운영 환경 배포 시:
```env
VITE_API_BASE_URL=https://your-domain.onrender.com
VITE_WS_BASE_URL=wss://your-domain.onrender.com
```

---

## 5. 공유 모듈 (`frontend/shared/`)

### `shared/config/`
- API 기본 URL, WebSocket URL 설정
- 환경변수 `VITE_API_BASE_URL`, `VITE_WS_BASE_URL` 읽기

### `shared/api/`
- REST API 호출 함수 (fetch 기반)
- 인증 헤더 자동 주입

### `shared/ws/`
- WebSocket 클라이언트 래퍼
- 메시지 타입별 핸들러 등록
- 재연결 로직

### `shared/types/`
- `EmotionSession`, `EmotionStep`, `EmotionCard`, `NeedCard` 등 공유 타입

---

## 6. 개발 서버 실행

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173 에서 실행
```

---

## 7. 빌드 & 프리뷰

```bash
npm run build       # dist/ 생성
npm run preview     # 빌드 결과 로컬 프리뷰
```

---

## 8. QA Demo UI와의 관계

| 항목 | QA Demo UI | React UI |
|------|-----------|---------|
| 위치 | `app/backend/demo_ui/` | `frontend/` |
| 기술 | Vanilla HTML/CSS/JS | React + TypeScript |
| 접속 | `/demo/emotion-analysis` | `localhost:5173/beta/chat` |
| 목적 | 회귀 테스트, 내부 QA | 실제 서비스 UI |
| 상태 | 완성, 유지 중 | 개발 중 |

QA Demo UI는 React UI와 별개로 운영됩니다. 대화 흐름에 변경이 생기면 두 UI 모두에서 동작 확인이 필요합니다.

---

## 9. 현재 개발 상황 및 다음 작업

**완료:**
- 전체 라우트 구조 설계 및 뼈대 컴포넌트
- 공유 API 클라이언트 및 WebSocket 클라이언트
- TypeScript 타입 정의
- Vite 빌드 설정

**진행 중 / 남은 작업:**
- `Chat.tsx`: WebSocket 연결, 실시간 스트리밍 메시지 렌더링, 종료 흐름 UI
- `Result.tsx`: 분석카드 데이터 시각화
- `Home.tsx`: 로그인(Google OAuth) 연동
- `admin/`: 세션 모니터링 기능 구현
- 인증 토큰 관리 (액세스 토큰 메모리 저장, 자동 갱신)
