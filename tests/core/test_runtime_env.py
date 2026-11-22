import pytest

from app.backend.core.runtime_env import is_local_runtime, is_test_runtime

TEST_SERVICE_ID = "srv-d9j0musm0tmc73a7ntv0"
PROD_SERVICE_ID = "srv-d267fau3jp1c73cmcr1g"


# (APP_ENV, RENDER_SERVICE_ID, RENDER_SERVICE_NAME) -> (is_local_runtime, is_test_runtime)
# None은 변수를 지운다. 무인증 웹테스트 폴백은 local, 프롬프트 연구 API는 test 판정을 쓴다.
@pytest.mark.parametrize(
    "app_env, service_id, service_name, expected_local, expected_test",
    [
        (None, None, None, False, False),
        ("production", None, None, False, False),
        ("development", None, None, True, True),
        ("local", None, None, True, True),
        ("DEVELOPMENT", None, None, True, True),
        ("Local", None, None, True, True),
        ("staging", None, None, False, False),
        (None, TEST_SERVICE_ID, None, False, True),
        (None, None, "Deep_me_test_server", False, True),
        (None, TEST_SERVICE_ID, "renamed-test-server", False, True),
        (None, PROD_SERVICE_ID, "Deep_me_V2", False, False),
        (None, None, "Deep_me_test_server_old", False, False),
        ("development", PROD_SERVICE_ID, "Deep_me_V2", True, True),
    ],
)
def test_runtime_decision_table(monkeypatch, app_env, service_id, service_name, expected_local, expected_test):
    for key, value in (
        ("APP_ENV", app_env),
        ("RENDER_SERVICE_ID", service_id),
        ("RENDER_SERVICE_NAME", service_name),
    ):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    assert is_local_runtime() is expected_local
    assert is_test_runtime() is expected_test
