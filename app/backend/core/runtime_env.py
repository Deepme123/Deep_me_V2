import os

# 테스트 런타임(웹테스트 무인증 우회, 프롬프트 연구 API 등)은 로컬/개발 환경에서만 허용한다.
# APP_ENV를 지정하지 않은 배포 환경(Render 등)은 기본값이 이 화이트리스트에 없으므로
# 관련 플래그가 실수로 켜져 있어도 발동하지 않는다.
_TEST_APP_ENVS = {"development", "local"}

# 단, Render 테스트 서비스는 APP_ENV 없이도 허용한다. RENDER_SERVICE_ID/NAME은 Render가
# 서비스마다 자동 주입한다. 실제 서비스는 render.yaml(Blueprint)로 만든 게 아니라서
# 이름이 render.yaml과 다르다 — 테스트 `Deep_me_test_server`, 운영 `Deep_me_V2`.
# 이름은 대시보드에서 바뀔 수 있으므로 불변인 서비스 ID를 우선 기준으로 쓴다.
# 운영 서비스(srv-d267fau3jp1c73cmcr1g / Deep_me_V2)는 어느 목록에도 없으므로 계속 차단된다.
_TEST_RENDER_SERVICE_IDS = {"srv-d9j0musm0tmc73a7ntv0"}
_TEST_RENDER_SERVICE_NAMES = {"Deep_me_test_server"}


def is_test_runtime() -> bool:
    app_env = os.getenv("APP_ENV", "production").lower()
    return (
        app_env in _TEST_APP_ENVS
        or os.getenv("RENDER_SERVICE_ID", "") in _TEST_RENDER_SERVICE_IDS
        or os.getenv("RENDER_SERVICE_NAME", "") in _TEST_RENDER_SERVICE_NAMES
    )
