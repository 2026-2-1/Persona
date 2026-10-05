from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from persona.api import FIXTURE_HTML
from persona.execution import run_session
from persona.models import Session


@pytest.mark.browser
def test_real_browser_captures_local_fixture(db_factory, settings):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(FIXTURE_HTML.encode())

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings.fixture_base_url = f"http://127.0.0.1:{server.server_port}/fixtures/shop"
    with db_factory() as db:
        session = Session(persona_name="실제 브라우저 시험")
        db.add(session)
        db.commit()
        session_id = session.id
    try:
        run_session(session_id, db_factory=db_factory, settings=settings)
        with db_factory() as db:
            session = db.get(Session, session_id)
            assert session.status == "succeeded", session.error
            assert [step.action for step in session.steps] == ["navigate", "click"]
            assert all(step.screenshot_after for step in session.steps)
        screenshots = list((settings.artifact_dir / session_id).glob("*.png"))
        assert len(screenshots) == 3
        assert all(path.read_bytes().startswith(b"\x89PNG") for path in screenshots)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
