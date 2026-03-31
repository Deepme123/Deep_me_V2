import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
IMPORT_SAFE_MODULES = [
    "app.db.session",
    "app.backend.db.session",
    "app.backend.routers.auth",
    "app.backend.main",
    "app.analyze.config",
    "app.analyze.services.llm_card",
    "app.analyze.main",
    "app.main",
]


def test_import_safe_modules_do_not_require_runtime_env_at_import_time():
    env = os.environ.copy()
    for key in [
        "DATABASE_URL",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
    ]:
        env.pop(key, None)

    script = """
import importlib
modules = %r
for mod in modules:
    importlib.import_module(mod)
print("ok")
""" % (IMPORT_SAFE_MODULES,)

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT_DIR,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
