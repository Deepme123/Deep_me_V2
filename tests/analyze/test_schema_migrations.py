import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parents[2]
TMP_DIR = ROOT_DIR / ".tmp-alembic-tests"


def _run_alembic(tmp_db: Path, revision: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{tmp_db.as_posix()}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=ROOT_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _table_names(tmp_db: Path) -> list[str]:
    conn = sqlite3.connect(tmp_db)
    try:
        cur = conn.cursor()
        cur.execute("select name from sqlite_master where type='table' order by name")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def _alembic_version(tmp_db: Path) -> str:
    conn = sqlite3.connect(tmp_db)
    try:
        cur = conn.cursor()
        cur.execute("select version_num from alembic_version")
        row = cur.fetchone()
        assert row is not None
        return row[0]
    finally:
        conn.close()


def _new_tmp_db(prefix: str) -> Path:
    TMP_DIR.mkdir(exist_ok=True)
    return TMP_DIR / f"{prefix}-{uuid4().hex}.db"


def test_base_schema_migration_excludes_emotioncard():
    tmp_db = _new_tmp_db("base-only")
    try:
        _run_alembic(tmp_db, "0001_base_schema")

        assert _table_names(tmp_db) == [
            "alembic_version",
            "emotionsession",
            "emotionstep",
            "refreshtoken",
            "task",
            "user",
        ]
        assert _alembic_version(tmp_db) == "0001_base_schema"
    finally:
        if tmp_db.exists():
            tmp_db.unlink()


def test_head_migration_includes_analysiscard():
    tmp_db = _new_tmp_db("head")
    try:
        _run_alembic(tmp_db, "head")

        assert _table_names(tmp_db) == [
            "alembic_version",
            "analysiscard",
            "deletionfeedback",
            "emotionsession",
            "emotionstep",
            "greetingmessagestat",
            "need_card_result",
            "need_card_score",
            "refreshtoken",
            "satisfactionrating",
            "task",
            "user",
            "user_need_selection",
        ]
        assert _alembic_version(tmp_db) == "0020_add_greeting_message_stat"
    finally:
        if tmp_db.exists():
            tmp_db.unlink()


def test_greeting_message_stat_created_after_0019():
    # 운영 DB 상황: 0015 없이 0019까지 적용돼 greetingmessagestat이 없다.
    tmp_db = _new_tmp_db("greeting-missing")
    try:
        _run_alembic(tmp_db, "0019_deletion_feedback")
        assert "greetingmessagestat" not in _table_names(tmp_db)

        _run_alembic(tmp_db, "head")

        conn = sqlite3.connect(tmp_db)
        try:
            rows = conn.execute(
                "select message_index, selected_count from greetingmessagestat order by message_index"
            ).fetchall()
        finally:
            conn.close()
        assert rows == [(i, 0) for i in range(10)]
    finally:
        if tmp_db.exists():
            tmp_db.unlink()


def test_greeting_message_stat_migration_keeps_existing_table():
    # 테스트 서버 DB 상황: 과거 0015로 이미 테이블이 있고 카운터가 쌓여 있다.
    tmp_db = _new_tmp_db("greeting-existing")
    try:
        _run_alembic(tmp_db, "0019_deletion_feedback")
        conn = sqlite3.connect(tmp_db)
        try:
            conn.execute(
                "create table greetingmessagestat ("
                "message_index integer not null primary key, "
                "selected_count integer not null default 0)"
            )
            conn.execute("insert into greetingmessagestat values (3, 7)")
            conn.commit()
        finally:
            conn.close()

        _run_alembic(tmp_db, "head")

        conn = sqlite3.connect(tmp_db)
        try:
            rows = conn.execute(
                "select message_index, selected_count from greetingmessagestat"
            ).fetchall()
        finally:
            conn.close()
        assert rows == [(3, 7)]
        assert _alembic_version(tmp_db) == "0020_add_greeting_message_stat"
    finally:
        if tmp_db.exists():
            tmp_db.unlink()
