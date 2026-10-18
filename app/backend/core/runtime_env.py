import os

# 테스트 런타임(웹테스트 무인증 우회, 프롬프트 연구 API 등)은 로컬/개발 환경에서만 허용한다.
# APP_ENV를 지정하지 않은 배포 환경(Render 등)은 기본값이 이 화이트리스트에 없으므로
# 관련 플래그가 실수로 켜져 있어도 발동하지 않는다.
_TEST_APP_ENVS = {"development", "local"}

# 단, Render 테스트 서비스는 APP_ENV 없이도 허용한다.
# RENDER_SERVICE_NAME은 Render가 서비스마다 자동 주입하며(deep-me-v2 / deep-me-v2-test),
# 운영 서비스(deep-me-v2)는 이 목록에 없으므로 계속 차단된다.
_TEST_RENDER_SERVICES = {"deep-me-v2-test"}


def is_test_runtime() -> bool:
    app_env = os.getenv("APP_ENV", "production").lower()
    render_service = os.getenv("RENDER_SERVICE_NAME", "")
    return app_env in _TEST_APP_ENVS or render_service in _TEST_RENDER_SERVICES
