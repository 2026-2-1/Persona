import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session as DatabaseSession

from persona.browser import BrowserRunner, CancellationRequested
from persona.config import Settings, get_settings
from persona.db import session_factory
from persona.models import Session, Step, utc_now

logger = logging.getLogger(__name__)
DatabaseFactory = Callable[[], DatabaseSession]


def run_session(
    session_id: str,
    *,
    db_factory: DatabaseFactory | None = None,
    settings: Settings | None = None,
    runner: BrowserRunner | None = None,
) -> bool:
    """Claim once across workers; every subsequent state change is conditional."""
    factory = db_factory or session_factory()
    config = settings or get_settings()
    with factory() as db:
        claimed = db.execute(
            update(Session)
            .where(Session.id == session_id, Session.status == "queued")
            .values(status="running", started_at=utc_now())
        )
        db.commit()
        if claimed.rowcount != 1:
            return False
        record = db.get(Session, session_id)
        persona_name, task_id = record.persona_name, record.task_id

    def is_cancelled() -> bool:
        with factory() as db:
            status = db.scalar(select(Session.status).where(Session.id == session_id))
            return status != "running"

    def record_step(values: dict[str, Any]) -> None:
        with factory() as db:
            db.add(Step(session_id=session_id, **values))
            db.commit()

    def finalize(status: str, error: str | None = None) -> None:
        with factory() as db:
            db.execute(
                update(Session)
                .where(Session.id == session_id, Session.status == "running")
                .values(status=status, error=error, finished_at=utc_now())
            )
            db.commit()

    try:
        (runner or BrowserRunner()).run(
            config, session_id, persona_name, task_id, is_cancelled, record_step
        )
        finalize("succeeded")
    except CancellationRequested:
        # The API has already persisted cancelled and finished_at.
        pass
    except Exception as exc:
        logger.exception("Session %s failed", session_id)
        finalize("technical_error", f"브라우저 실행 실패 ({type(exc).__name__})")
    return True
