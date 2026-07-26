# CI/CD 및 배포 프로세스

---

## 1. CI 파이프라인 (`.github/workflows/ci.yml`)

`main`으로의 **Pull Request**에서만 트리거됩니다(`on: pull_request: branches: [main]`
— push 자체나 다른 브랜치로의 PR에서는 돌지 않음).

| Job | 내용 |
|-----|------|
| `test` | `pip install -r requirements.txt` → `pytest tests/ -v` |
| `migrations` | Postgres 16 서비스 컨테이너 기동 → `alembic upgrade head` → `alembic check`(모델 ↔ 마이그레이션 드리프트 검사) |

두 job 모두 `JWT_SECRET_KEY`/`JWT_REFRESH_SECRET`을 CI 전용 더미 값으로 주입합니다
(서버 시작 시 필수 검증 때문). `migrations` job은 실제 Postgres에 마이그레이션을
끝까지 적용해보고, `alembic revision --autogenerate`가 추가로 뭔가를
생성하려 하지 않는지(즉 SQLModel 정의와 마이그레이션 히스토리가 일치하는지)
`alembic check`로 확인합니다 — 마이그레이션 파일을 깜빡 잊고 커밋 안 했을 때
여기서 잡힙니다.

> CI는 **품질 게이트**일 뿐 배포를 트리거하지 않습니다. 배포는 아래 §2의
> 별도 GitHub 웹훅(`/webhook/github`)이 담당합니다.

---

## 2. 배포 트리거 (`app/backend/routers/deploy_webhook.py`)

GitHub Actions가 아니라, 이 저장소 자신이 노출하는 `POST /webhook/github`
엔드포인트가 GitHub → 백엔드로 직접 웹훅을 받아 처리합니다. GitHub 저장소
Settings → Webhooks에 이 URL이 등록되어 있어야 동작합니다.

### push 이벤트 (`main` 브랜치)

```
GitHub main push
    │
    ▼
POST /webhook/github  (X-GitHub-Event: push)
    │  서명 검증 (GITHUB_WEBHOOK_SECRET, HMAC-SHA256)
    │  branch != main 이면 무시
    ▼
Render Deploy Hook 호출 (RENDER_DEPLOY_HOOK_URL)
    │
    ├─ RENDER_API_KEY + RENDER_SERVICE_ID 설정된 경우
    │     → 최대 10분간 10초 간격으로 배포 상태 폴링
    │     → live/build_failed/update_failed/canceled/deactivated 감지
    │     → 결과를 Discord로 알림 (성공/실패 + 배포 URL)
    │
    └─ 미설정인 경우
          → 트리거만 하고 "트리거 완료" 알림만 전송 (실제 성공 여부는 Render 대시보드에서 확인해야 함)
```

### pull_request 이벤트 (`main`으로 merge)

```
PR이 main으로 merged
    │
    ▼
POST /webhook/github  (X-GitHub-Event: pull_request, action=closed, merged=true, base=main)
    │  서명 검증
    ▼
PR의 전체 커밋 목록을 GitHub API로 조회 (commits_url — GitHub API 호스트인지 검증, SSRF 방지)
    │
    ▼
커밋 목록을 텍스트 파일로 만들어 Discord 채널에 첨부 전송
```

이 두 흐름은 완전히 분리되어 있습니다 — push 이벤트는 실제 배포를 트리거하고,
pull_request 이벤트는 배포와 무관하게 "무엇이 merge됐는지" 기록만 남깁니다.

### 관련 환경변수

| 변수 | 용도 |
|------|------|
| `GITHUB_WEBHOOK_SECRET` | 웹훅 서명 검증. 미설정 시 서명 검증을 통째로 건너뜀(로컬/테스트 편의용 — 운영에서는 반드시 설정) |
| `RENDER_DEPLOY_HOOK_URL` | Render Deploy Hook URL. 미설정 시 배포가 트리거되지 않고 실패 알림만 감 |
| `RENDER_API_KEY` / `RENDER_SERVICE_ID` | 배포 상태 폴링용 (선택 — 없으면 트리거 성공만 확인) |
| `DISCORD_WEBHOOK_URL` | 배포/PR 알림을 받을 채널. `DISCORD_ERROR_WEBHOOK_URL`(에러 로그용)과는 별개 |

---

## 3. 배포 절차

**이 프로젝트에는 별도의 스테이징 환경이 없습니다.** `render.yaml`에 정의된
프로덕션 서비스(`deep-me-v2`) 하나만 존재하며, `main` 브랜치에 대한 push가
곧 프로덕션 배포입니다.

실제 흐름 (CLAUDE.md 브랜치 전략과 결합):

1. `feat/*` / `fix/*` 브랜치에서 작업 → `develop`에 PR
2. `develop`에서 통합 확인 (자동화된 CI는 없음 — `ci.yml`은 `main` PR에서만 동작)
3. `develop` → `main` PR 생성 → **`ci.yml`이 실행**되어 테스트 + 마이그레이션
   드리프트 검사를 통과해야 함 → 리뷰 필수(CLAUDE.md)
4. PR을 `main`에 merge
   - GitHub push 웹훅이 `/webhook/github`을 호출 → Render Deploy Hook 트리거
   - Render가 `preDeployCommand: alembic upgrade head` 실행 후 새 인스턴스 기동
   - `healthCheckPath: /health/db`가 통과해야 트래픽 전환
   - Discord로 배포 성공/실패 알림
   - 동시에 PR 커밋 목록이 Discord에 별도로 기록됨

즉 "스테이징 → 프로덕션 승격" 단계는 없고, `develop`에서의 수동/육안 확인이
사실상 스테이징 검증을 대신하는 구조입니다. 별도 스테이징 Render 서비스가
필요하다면 `render.yaml`에 서비스를 하나 더 추가하고 `develop` push에 대한
웹훅을 별도로 구성해야 하는데, 현재는 그렇게 되어 있지 않습니다.

---

## 4. 롤백 방법

**자동화된 롤백 메커니즘은 없습니다.** 아래는 실제 가능한 수동 절차입니다.

### 4.1 애플리케이션 코드 롤백

옵션 A — **Render 대시보드에서 이전 배포로 수동 롤백** (가장 빠름, DB
마이그레이션이 얽혀있지 않을 때만 안전):
- Render 서비스 → Deploys 탭 → 이전 성공 배포 선택 → Rollback

옵션 B — **`main`에 revert 커밋을 push** (기록이 남고, 웹훅이 다시 정상
배포 파이프라인을 태움):
```bash
git revert <문제_커밋_SHA>
git push origin main   # 팀 정책상 보통 PR을 거쳐야 함 — 긴급 hotfix는 예외 적용 여부를 팀과 확인
```
`main` 직접 push/force-push는 CLAUDE.md 정책상 금지이므로, 급한 경우에도
PR 리뷰를 생략하지 않는 것이 원칙입니다.

### 4.2 DB 마이그레이션 롤백

```bash
alembic downgrade -1        # 마지막 마이그레이션 한 단계만 되돌림
alembic downgrade <revision>  # 특정 리비전까지
```

> ⚠️ 애플리케이션 코드 롤백과 DB 마이그레이션 롤백은 **순서를 맞춰야
> 합니다.** 코드를 먼저 되돌리고 DB가 새 스키마인 채로 남으면(또는 반대의
> 경우) 컬럼 누락/타입 불일치로 500 에러가 날 수 있습니다. 가능하면
> 마이그레이션이 하위 호환되게(컬럼 추가는 NULL 허용, 컬럼 삭제는 별도
> 배포로 분리) 설계해서 애초에 동시 롤백이 필요 없게 하는 것이 안전합니다.

### 4.3 LLM 프로바이더 롤백

프로바이더/모델 문제로 인한 장애는 배포 롤백 없이 환경변수만 바꿔도
해결되는 경우가 많습니다 — [DEPLOYMENT.md](./DEPLOYMENT.md) §5 참고.
`.env.example`에 `LLM_PROVIDER=openai`가 "Emergency rollback target"으로
명시되어 있습니다.

> `RUN.md`는 프로바이더 전환/롤백 절차가 `docs/env-provider-migration.md`에
> 있다고 안내하지만, 실제로 이 저장소에 그 파일은 없습니다(끊긴 링크).
> 프로바이더 전환은 위 DEPLOYMENT.md §5가 현재 유효한 문서입니다.
