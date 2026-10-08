# 프론트엔드

> 프론트엔드는 예전에 계획했던 React + Vite 웹 앱이 아니라 **Flutter 모바일 앱**으로
> 개발되고 있습니다. 별도 레포([DeepMe-frontend](https://github.com/Deepme123/DeepMe-frontend))로
> 관리되며 `frontend/`에 클론해 사용합니다 — `.gitignore`에 등록되어 있어 이 백엔드
> 레포의 git 이력에는 포함되지 않습니다. 프론트엔드 자체의 상세 가이드는
> `frontend/CLAUDE.md`에 있습니다.

---

## 1. 기술 스택

| 항목 | 내용 |
|------|------|
| 프레임워크 | Flutter (Dart), SDK `>=3.3.0`, Flutter `>=3.0.0` |
| 상태 관리 | 싱글톤 서비스 + `StreamController.broadcast()` (별도 상태관리 라이브러리 없음) |
| 로컬 저장소 | `shared_preferences` (JWT 토큰, 유저 데이터) |
| 인증 | `google_sign_in` (Google OAuth) |
| HTTP | `dio` |
| WebSocket | `web_socket_channel` |
| 오디오/영상 | `audioplayers`, `video_player` |
| 컴포넌트 카탈로그 | `widgetbook` (개발용, `widgetbook_app.dart`) |
| 대상 플랫폼 | Android, iOS, Web (android/, ios/, web/ 디렉토리 모두 존재) |

---

## 2. 디렉토리 구조

```
frontend/
├── lib/
│   ├── main.dart                    # 앱 진입점 (MaterialApp, LoginScreen에서 시작)
│   ├── widgetbook_app.dart          # 컴포넌트 카탈로그 진입점 (개발용)
│   ├── core/
│   │   ├── config/api_config.dart   # API/WebSocket base URL, 엔드포인트 상수
│   │   ├── network/dio_client.dart      # Dio 인스턴스 팩토리 (로깅/에러 인터셉터)
│   │   └── network/websocket_client.dart # WebSocket 연결/전송 유틸리티
│   ├── services/
│   │   ├── auth_service.dart         # 싱글톤: Google 로그인 → 서버 JWT 교환
│   │   └── emotion_chat_service.dart # 싱글톤: WS 연결, 재연결, 메시지 스트리밍
│   ├── screens/
│   │   ├── login_screen.dart          # 인증 상태 확인 → Google 로그인
│   │   └── emotion_chat_screen.dart   # 메인 채팅 화면 (배경음악 포함)
│   ├── widgets/                       # 채팅 버블, 무드 카드, 분석 결과 카드 등 UI 컴포넌트
│   ├── models/
│   │   ├── chat_message.dart
│   │   └── auth_response.dart
│   └── constants/                     # 색상, 텍스트 스타일, 여백, 아이콘 등 디자인 토큰
├── assets/
│   ├── images/
│   └── videos/                        # 배경 영상 + BGM(mp3)
├── android/ ios/ web/                 # 플랫폼별 네이티브 프로젝트
├── test/
├── pubspec.yaml
└── analysis_options.yaml
```

과거 문서에 있던 `apps/beta`, `apps/admin`, React Router 기반 라우트 구조,
`shared/` 공유 모듈 디렉토리는 실제로 존재하지 않습니다 — 이는 검토 단계에서
계획됐던 웹 UI 구조이며 실제 구현은 이 Flutter 앱으로 대체되었습니다.

---

## 3. 백엔드 연동 방식

`lib/core/config/api_config.dart`에 baseURL이 **하드코딩**되어 있고, 별도의
`.env`/`--dart-define` 기반 환경 분리는 아직 없습니다.

```dart
static const String serverHost = 'deep-me-v1.onrender.com';
static const String baseUrl = 'https://$serverHost';
static const String websocketUrl = 'wss://$serverHost';
static const String googleAuthEndpoint = '/auth/google/access';
static const String websocketEmotionEndpoint = '/ws/emotion';
```

로컬 백엔드(`http://localhost:8000`)로 붙여 테스트하려면 이 파일의 값을 직접
바꿔야 합니다. 로컬/운영을 분리하고 싶다면 이 상수들을 환경변수 또는
`--dart-define` 기반으로 바꾸는 작업이 필요합니다(아직 미구현).

### 인증 흐름

1. `AuthService`가 `google_sign_in`으로 Google 로그인 → Google Access Token 획득
2. `POST /auth/google/access`로 Google Access Token을 보내 서버 JWT(Access/Refresh)로 교환
3. WebSocket 연결(`wss://.../ws/emotion`) 시 JWT를 함께 전달해 인증

### 실시간 채팅

- `EmotionChatService`가 `WebSocketClient`로 `/ws/emotion`에 연결하고, 지수
  백오프 재연결(최대 3회) + 하트비트로 연결 상태를 관리합니다.
- 서버가 보내는 `message_start`/`message_delta`/`message`/`message_end`
  스트림을 받아 타이핑 효과로 렌더링합니다 (현재 백엔드 WS 프로토콜의 실제
  메시지 타입은 `API.md` 3장 참조 — 프론트 쪽 문서(`frontend/CLAUDE.md`)에는
  이전 버전 이름인 `token`/`complete` 등으로 적혀 있을 수 있어 실제 코드
  기준으로 교차 확인이 필요합니다).
- 긴 AI 응답은 여러 채팅 버블로 자동 분할해 800ms 간격으로 순차 표시합니다.

---

## 4. 개발 서버 실행

```bash
cd frontend
flutter pub get
flutter run                    # 연결된 기기/에뮬레이터에서 실행
```

```bash
flutter build apk --release    # Android 릴리스 빌드
flutter build ios --release    # iOS 릴리스 빌드 (macOS 전용)
flutter test                   # 테스트 실행
flutter clean                  # 빌드 캐시 정리
```

---

## 5. QA Demo UI와의 관계

과거 `app/backend/demo_ui/`(서버 렌더링 Vanilla HTML/JS QA 데모, `/demo/emotion-analysis`)가
있었으나 **제거되었습니다**. 현재 WebSocket 흐름을 눈으로 확인하려면 이
Flutter 앱을 직접 실행하거나, `wscat` 등으로 `/ws/emotion`에 직접 연결해야
합니다.

---

## 6. 현재 개발 상황

**완료:**
- Google OAuth 로그인 → 서버 JWT 교환 흐름
- WebSocket 기반 실시간 채팅 화면(스트리밍 렌더링, 메시지 분할, 재연결)
- 채팅 배경음악/영상 등 감성 UI 요소

**참고할 점 / 남은 작업:**
- 로컬/운영 API 엔드포인트가 코드에 하드코딩되어 있어 로컬 백엔드 대상
  개발 시 `api_config.dart`를 직접 수정해야 함
- 분석카드·욕구카드·태스크 등 백엔드가 이미 제공하는 기능 다수가 아직
  UI에 반영되지 않았을 수 있음 — `frontend/lib/widgets/`에 관련 위젯
  (`situation_card.dart`, `mood_card.dart`, `desire_card_image.dart`,
  `behavior_pattern_card.dart` 등)이 존재하나 실제 화면 연동 여부는
  프론트엔드 레포에서 직접 확인 필요
- 백엔드 WS 프로토콜이 최근 크게 바뀌었으므로(서버 자동 세션 오픈, 자동
  인사, `message_*` 이벤트 이름) 프론트엔드 쪽 `EmotionChatService`가 이
  변경을 반영하고 있는지 별도 확인이 필요함
