# 프론트엔드

> 프론트엔드는 **Flutter 모바일 앱**입니다 (과거 계획됐던 React 웹 UI가 아님).
> [DeepMe-frontend](https://github.com/Deepme123/DeepMe-frontend) 레포를
> `frontend/`에 클론해서 사용하며, `frontend/`는 `.gitignore`에 등록되어 있어
> 이 백엔드 레포의 git 이력에는 포함되지 않습니다. 아래 내용은 백엔드
> 개발자가 API 계약을 맞추는 데 필요한 수준으로 요약한 것이며, 프론트엔드
> 작업 자체는 `frontend/CLAUDE.md`(그 레포의 가이드)를 따로 참고해야 합니다.

---

## 1. 기술 스택

| 항목 | 버전/값 |
|------|------|
| Flutter SDK | 3.0+ |
| Dart SDK | 3.3+ |
| 상태 관리 | 싱글톤 서비스 + `StreamController` (Provider/Bloc 등 프레임워크 미사용) |
| 네트워크 | `dio` (HTTP), `web_socket_channel` (WebSocket) |
| 인증 | `google_sign_in` v7 |
| 로컬 저장소 | `shared_preferences` |
| 컴포넌트 카탈로그 | `widgetbook` (Firebase Hosting에 별도 배포) |

---

## 2. 디렉토리 구조

```
frontend/
├── lib/
│   ├── main.dart                       # 앱 진입점
│   ├── core/
│   │   ├── config/api_config.dart      # API/WebSocket base URL, 엔드포인트 상수
│   │   ├── network/
│   │   │   ├── dio_client.dart         # HTTP 클라이언트 팩토리
│   │   │   └── websocket_client.dart   # WebSocket 클라이언트 유틸리티
│   │   └── utils/preferences_helper.dart  # SharedPreferences 래퍼
│   ├── constants/                      # 색상/텍스트/패딩 등 UI 상수
│   ├── models/
│   │   ├── auth_response.dart
│   │   └── chat_message.dart
│   ├── screens/
│   │   ├── login_screen.dart           # Google 로그인
│   │   └── emotion_chat_screen.dart    # 실시간 감정 채팅 (배경음악 포함)
│   ├── widgets/                        # 메시지 버블, 분석/욕구 카드 등 공용 컴포넌트
│   └── services/
│       ├── auth_service.dart           # Google OAuth + 서버 토큰 교환 (싱글톤)
│       └── emotion_chat_service.dart   # WebSocket 채팅 서비스 (싱글톤)
├── widgetbook_app.dart                 # 위젯북 엔트리(컴포넌트 카탈로그)
├── assets/{images,videos}/
└── pubspec.yaml
```

---

## 3. 백엔드 연동 지점

`frontend/lib/core/config/api_config.dart`에 하드코딩된 값 기준(로컬 `.env` 방식이
아님 — 값을 바꾸려면 이 파일을 직접 수정해야 함):

```dart
baseUrl       = "https://deep-me-v1.onrender.com"
websocketUrl  = "wss://deep-me-v1.onrender.com"
```

| 백엔드 엔드포인트 | 프론트엔드 사용처 |
|---|---|
| `POST /auth/google/access` | `AuthService` — Google access token → 서버 JWT 교환 |
| `WS /ws/emotion` | `EmotionChatService` — 실시간 감정 대화 |

인증 흐름 요약 (자세한 서버 쪽 동작은 [ARCHITECTURE.md](./ARCHITECTURE.md) §4 참고):
1. Google Sign-In으로 Google access token 획득
2. `POST /auth/google/access`로 서버 JWT 교환
3. JWT를 `SharedPreferences`에 저장, WebSocket 연결 시 사용

WebSocket 쪽 유의사항:
- 메시지 타입은 이 저장소의 `MSG_*` 프로토콜([API.md](./API.md) §3)과 이름이
  다르게 매핑되어 있음 — 프론트는 `connected`/`sessionStart`/`welcome`/
  `userMessage`/`token`/`complete`/`error` 같은 내부 이벤트명을 씀. 백엔드
  메시지 타입 필드(`type`)를 파싱해서 이 이벤트로 변환하는 로직이
  `EmotionChatService`에 있음.
- 긴 AI 응답은 여러 버블로 나눠 800ms 간격으로 순차 표시(프론트 UX 로직,
  서버는 하나의 `stream_end`로 전체 텍스트를 보냄).
- 연결 끊김 시 최대 3회 지수 백오프 재연결, 하트비트 모니터링.

---

## 4. QA Demo UI와의 관계

과거 있었던 백엔드 서버 렌더링 QA 데모(`app/backend/demo_ui/`,
`/demo/emotion-analysis`)는 **제거되었습니다.** 현재는 Flutter 앱이 유일한
클라이언트이며, 로컬에서 WebSocket 흐름을 확인하려면 Flutter 앱을 직접
실행하거나 `/docs`(Swagger UI)로 스키마만 확인해야 합니다.

---

## 5. 현재 개발 상황

**구현됨:**
- Google 로그인 화면, 서버 JWT 교환
- 실시간 감정 대화 화면(WebSocket 스트리밍, 메시지 분할 표시, 배경음악)
- 분석카드/욕구카드 관련 위젯(`analysis_chip`, `mood_card`, `desire_card_image`,
  `behavior_pattern_card` 등) — 화면 연동 범위는 `frontend/lib/screens/`가
  두 화면(`login_screen`, `emotion_chat_screen`)뿐이라 위젯 상당수가 아직
  화면에 완전히 통합되지 않았을 수 있음. 최신 화면 목록은 `frontend/lib/screens/`
  실제 파일 목록으로 확인할 것.

**백엔드 관점에서 주의할 점:**
- 프론트가 `/auth/google/access`(Google access token 교환)만 쓰고 있어서,
  `/auth/google`(id_token 방식)이나 `/auth/callback`(웹 OAuth 리디렉션)을
  변경할 때는 실제 사용 여부를 프론트 코드로 재확인해야 함.
- API 계약을 바꿀 때는 optional 필드 + 폴백으로 하위 호환을 유지하고,
  프론트 레포는 이 세션에서 직접 건드리지 않음(프론트 개발자에게 별도 요청).
