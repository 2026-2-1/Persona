import pytest
from sqlalchemy import update

from persona.browser import CancellationRequested, allowed_url
from persona.execution import run_session
from persona.models import Session, utc_now


def queued_session(db_factory):
    with db_factory() as db:
        record = Session(persona_name="첫 방문")
        db.add(record)
        db.commit()
        return record.id


class FakeRunner:
    def __init__(self, callback=None, error=None):
        self.calls = 0
        self.callback = callback
        self.error = error

    def run(self, settings, session_id, persona_name, task_id, is_cancelled, on_step):
        self.calls += 1
        on_step(
            {
                "step_no": 1,
                "action": "navigate",
                "url": settings.fixture_base_url,
                "description": "fixture",
                "status": "succeeded",
                "screenshot_before": None,
                "screenshot_after": None,
            }
        )
        if self.callback:
            self.callback(session_id)
        if self.error:
            raise self.error
        if is_cancelled():
            raise CancellationRequested


def test_worker_claim_once_and_preserves_steps(db_factory, settings):
    session_id = queued_session(db_factory)
    runner = FakeRunner()
    assert run_session(session_id, db_factory=db_factory, settings=settings, runner=runner)
    assert not run_session(session_id, db_factory=db_factory, settings=settings, runner=runner)
    assert runner.calls == 1
    with db_factory() as db:
        session = db.get(Session, session_id)
        assert session.status == "succeeded"
        assert session.started_at is not None and session.finished_at is not None
        assert len(session.steps) == 1


def test_failure_preserves_completed_steps(db_factory, settings):
    session_id = queued_session(db_factory)
    run_session(
        session_id,
        db_factory=db_factory,
        settings=settings,
        runner=FakeRunner(error=RuntimeError("private error detail")),
    )
    with db_factory() as db:
        session = db.get(Session, session_id)
        assert session.status == "technical_error"
        assert len(session.steps) == 1
        assert "RuntimeError" in session.error and "private" not in session.error


@pytest.mark.parametrize("exception", [None, RuntimeError("late failure")])
def test_cancel_during_running_cannot_be_overwritten(db_factory, settings, exception):
    session_id = queued_session(db_factory)

    def cancel(identifier):
        with db_factory() as db:
            db.execute(
                update(Session)
                .where(Session.id == identifier)
                .values(status="cancelled", finished_at=utc_now())
            )
            db.commit()

    run_session(
        session_id,
        db_factory=db_factory,
        settings=settings,
        runner=FakeRunner(callback=cancel, error=exception),
    )
    with db_factory() as db:
        session = db.get(Session, session_id)
        assert session.status == "cancelled"
        assert session.error is None
        assert len(session.steps) == 1


def test_cancelled_queue_is_not_claimed(db_factory, settings):
    session_id = queued_session(db_factory)
    with db_factory() as db:
        db.get(Session, session_id).status = "cancelled"
        db.commit()
    runner = FakeRunner()
    assert not run_session(session_id, db_factory=db_factory, settings=settings, runner=runner)
    assert runner.calls == 0


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("http://127.0.0.1:8000/fixtures/shop", True),
        ("http://127.0.0.1:8000/other-local-resource", True),
        ("http://127.0.0.1:8001/fixtures/shop", False),
        ("https://127.0.0.1:8000/fixtures/shop", False),
        ("http://localhost:8000/fixtures/shop", False),
        ("https://example.com", False),
        ("file:///etc/passwd", False),
        ("http://user:password@127.0.0.1:8000", False),
    ],
)
def test_origin_allowlist(url, allowed):
    assert allowed_url(url, "http://127.0.0.1:8000/fixtures/shop") is allowed
