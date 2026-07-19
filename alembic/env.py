import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import JSON, engine_from_config, pool
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel

from app.db.session import get_database_url

# Ensure project root is on sys.path for imports.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_database_url())

# Import all models so SQLModel.metadata is populated.
from app.backend.models import user, task, refresh_token, emotion  # noqa: F401,E402
from app.analyze import models as analyze_models  # noqa: F401,E402
from app.desire import models as desire_models  # noqa: F401,E402

target_metadata = SQLModel.metadata


def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    # 일부 컬럼은 postgres에서 의도적으로 JSONB로 운영되지만, SQLModel 컬럼은
    # sqlite 테스트 호환을 위해 범용 JSON으로 선언되어 있다(0003/0010 마이그레이션
    # 참고). 이 조합은 실제 드리프트가 아니므로 비교에서 제외한다.
    if type(metadata_type) is JSON and isinstance(inspected_type, JSONB):
        return False
    return None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=compare_type,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=compare_type,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
