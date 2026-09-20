from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import session_scope
from app.backend.services.account_deletion import sweep_due_account_deletions

log = logging.getLogger(__name__)

SWEEP_INTERVAL_MINUTES = int(os.getenv("ACCOUNT_DELETION_SWEEP_INTERVAL_MINUTES", "5"))

_scheduler: BackgroundScheduler | None = None


def _run_sweep() -> None:
    with session_scope() as db:
        deleted = sweep_due_account_deletions(db)
    if deleted:
        log.info("account deletion sweep: %d개 계정 삭제 완료", deleted)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_sweep,
        "interval",
        minutes=SWEEP_INTERVAL_MINUTES,
        id="account_deletion_sweep",
    )
    _scheduler.start()


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
