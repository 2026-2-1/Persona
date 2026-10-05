import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from persona.api import get_publisher
from persona.models import Session


def test_health_and_fixture(client):
    assert client.get("/health").json() == {
        "status": "ok",
        "service": "persona-api",
        "model_provider": "mock",
    }
    fixture = client.get("/fixtures/shop")
    assert fixture.status_code == 200
    assert 'id="show-info"' in fixture.text
    assert 'id="product-info" hidden' in fixture.text


def test_create_list_and_read_persisted_session(client, published):
    response = client.post("/sessions", json={"persona_name": " 첫 방문 ", "task_id": "T02"})
    assert response.status_code == 202
    session = response.json()
    assert session["status"] == "queued"
    assert session["persona_name"] == "첫 방문"
    assert session["steps"] == []
    assert session["steps_count"] == 0
    assert session["created_at"].endswith("Z")
    assert published == [session["id"]]
    assert client.get(f"/sessions/{session['id']}").json() == session
    assert client.get("/sessions").json()[0]["id"] == session["id"]


def test_idempotency_reuses_result_and_rejects_changed_payload(client, published):
    headers = {"Idempotency-Key": "create-fixture-session"}
    first = client.post("/sessions", json={}, headers=headers)
    repeat = client.post("/sessions", json={}, headers=headers)
    assert first.status_code == repeat.status_code == 202
    assert repeat.json()["id"] == first.json()["id"]
    assert len(published) == 1
    conflict = client.post("/sessions", json={"persona_name": "다른 이름"}, headers=headers)
    assert conflict.status_code == 409


def test_idempotency_is_enforced_by_database(db_factory):
    with db_factory() as db:
        db.add(Session(persona_name="첫 방문", idempotency_key="same-key"))
        db.commit()
        db.add(Session(persona_name="두 번째", idempotency_key="same-key"))
        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.parametrize(
    "payload",
    [{"persona_name": "  "}, {"task_id": "T99"}, {"url": "https://example.com"}],
)
def test_reject_invalid_or_arbitrary_task_payload(client, payload):
    assert client.post("/sessions", json=payload).status_code == 422


def test_queue_failure_is_visible_and_terminal(client, db_factory):
    def failing_publish(session_id):
        raise ConnectionError("secret broker connection details")

    client.app.dependency_overrides[get_publisher] = lambda: failing_publish
    response = client.post("/sessions", json={})
    assert response.status_code == 503
    session_id = response.json()["detail"]["session_id"]
    with db_factory() as db:
        session = db.scalar(select(Session).where(Session.id == session_id))
        assert session.status == "technical_error"
        assert session.finished_at is not None
        assert "secret" not in session.error


def test_cancel_is_durable_and_idempotent(client):
    session_id = client.post("/sessions", json={}).json()["id"]
    first = client.post(f"/sessions/{session_id}/cancel")
    repeat = client.post(f"/sessions/{session_id}/cancel")
    assert first.json()["status"] == "cancelled"
    assert repeat.json()["finished_at"] == first.json()["finished_at"]
    assert client.get(f"/sessions/{session_id}").json()["status"] == "cancelled"


def test_unknown_and_malformed_session(client):
    assert client.get("/sessions/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/sessions/not-a-uuid").status_code == 422


def test_artifact_endpoint_does_not_expose_other_files(client, settings):
    session_id = "00000000-0000-0000-0000-000000000000"
    folder = settings.artifact_dir / session_id
    folder.mkdir(parents=True)
    (folder / "1-after.png").write_bytes(b"fixture-image")
    (folder / "secret.txt").write_text("do not expose")
    assert client.get(f"/artifacts/{session_id}/1-after.png").content == b"fixture-image"
    assert client.get(f"/artifacts/{session_id}/secret.txt").status_code == 404
    assert client.get(f"/artifacts/{session_id}/../secret.txt").status_code == 404
