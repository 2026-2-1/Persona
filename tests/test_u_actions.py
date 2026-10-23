from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

import pytest
from pydantic import ValidationError

from uxagent.actions import ActionExecutor
from uxagent.browser import BrowserSession
from uxagent.fast_loop import FastLoop
from uxagent.offline import install_scenario_origin_guard
from uxagent.runner import load_study
from uxagent.schemas import Action, Observation, UAction, UActions

ROOT = Path(__file__).resolve().parents[1]


def action(kind, **fields):
    return Action(type=kind, observation_id="stale-observation", tab_id="not-active", **fields)


def test_u_action_schema_accepts_full_step_dispatch_and_rejects_unknown_fields():
    values = [
        {"action": "mouse_click", "at_x": 2, "at_y": 3, "description": "click"},
        {"action": "raw_type", "text": "query", "description": "type"},
        {"action": "scroll", "direction": "left", "amount": 17, "description": "scroll"},
        {"action": "key_press", "key": "Control+A", "description": "key"},
        {"action": "forward", "description": "forward"},
        {"action": "refresh", "description": "refresh"},
    ]
    assert [UAction.model_validate(item).action for item in values] == [
        "mouse_click", "raw_type", "scroll", "key_press", "forward", "refresh"
    ]
    with pytest.raises(ValidationError):
        UAction.model_validate({"action": "scroll", "direction": "diagonal", "amount": 1, "description": "bad"})
    with pytest.raises(ValidationError):
        UAction.model_validate({"action": "mouse_click", "at_x": 1, "description": "bad"})


def test_u_action_adapter_preserves_action_fields_and_translates_tab_indices():
    observation = Observation(
        observation_id="obs-host", tab_id="tab-1", url="https://first.test", title="", html="",
        tabs=[
            {"id": "tab-1", "title": "first", "url": "https://first.test", "active": True},
            {"id": "tab-2", "title": "second", "url": "https://second.test", "active": False},
        ],
    )
    proposal = UActions.model_validate({"actions": [{
        "action": "scroll", "direction": "right", "amount": 9999, "description": "scroll sideways"
    }]})
    adapted, finish = FastLoop.adapt_action(proposal.actions[0], observation)
    assert adapted.type == "scroll"
    assert adapted.scroll_direction == "right" and adapted.scroll_amount == 9999
    assert adapted.observation_id == "obs-host" and adapted.tab_id == "tab-1"
    assert finish is None

    proposal = UActions.model_validate({"actions": [{
        "action": "switch_tab", "tab_id": 1, "description": "switch"
    }]})
    adapted, _ = FastLoop.adapt_action(proposal.actions[0], observation)
    assert adapted.target_tab_id == "tab-2"


def test_study_start_origin_does_not_require_an_allowed_origins_entry(tmp_path):
    raw = json.loads((ROOT / "configs/study.json").read_text(encoding="utf-8"))
    raw["start_url"] = "https://www.decathlon.co.kr/search?query=running"
    raw["allowed_origins"] = []
    raw["persona_file"] = str(ROOT / "configs/persona.json")
    path = tmp_path / "study.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    config, _, _ = load_study(path)
    assert config.start_url == raw["start_url"]
    assert config.allowed_origins == []


async def _start(browser, markup):
    async def route(request_route):
        await request_route.fulfill(body=markup, content_type="text/html")

    await browser.context.route("https://first.test/**", route)
    await browser.active.goto("https://first.test/start")


@pytest.mark.asyncio
async def test_executor_uses_semantic_dom_target_without_observation_capability_or_origin_gates():
    async with BrowserSession(False) as browser:
        await _start(browser, """<button parser-semantic-id='arbitrary' onclick="document.body.dataset.clicked='yes'">button</button>""")
        executor = ActionExecutor(browser, ["https://unrelated.test"])
        result = await executor.execute(action("click", target_id="arbitrary"))
        assert result.ok
        assert await browser.active.locator("body").get_attribute("data-clicked") == "yes"


@pytest.mark.asyncio
async def test_executor_supports_unrestricted_key_input_coordinates_scroll_and_clear():
    async with BrowserSession(False) as browser:
        await _start(browser, """<input id='field' parser-semantic-id='field' autofocus>
            <div style='width:3000px;height:200px'>wide page</div>
            <button style='position:absolute;left:30px;top:40px' onclick="document.body.dataset.clicked='yes'">go</button>
            <script>document.addEventListener('keydown',e=>document.body.dataset.keys=(document.body.dataset.keys||'')+e.key)</script>""")
        executor = ActionExecutor(browser, [])
        assert (await executor.execute(action("key_press", key="Control+A"))).ok
        assert "Control" in (await browser.active.locator("body").get_attribute("data-keys"))
        assert (await executor.execute(action("raw_type", text="typed"))).ok
        assert await browser.active.locator("#field").input_value() == "typed"
        assert (await executor.execute(action("clear", target_id="field"))).ok
        assert await browser.active.locator("#field").input_value() == ""
        assert (await executor.execute(action("mouse_click", at_x=40, at_y=50))).ok
        assert await browser.active.locator("body").get_attribute("data-clicked") == "yes"
        scroll = await executor.execute(action("scroll", scroll_direction="right", scroll_amount=200))
        assert scroll.ok and scroll.interaction["moved"]
        assert scroll.interaction["direction"] == "right"


@pytest.mark.asyncio
async def test_executor_supports_navigation_redirect_history_and_tabs_across_origins():
    second = ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
    second.daemon_threads = True
    second.callback = lambda path: (200, "<title>second</title><p>second</p>")
    Thread(target=second.serve_forever, daemon=True).start()
    second_url = f"http://127.0.0.1:{second.server_port}"
    first = ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
    first.daemon_threads = True
    first.callback = lambda path: (302, second_url + "/final") if path == "/redirect" else (200, "<title>first</title><p>first</p>")
    Thread(target=first.serve_forever, daemon=True).start()
    first_url = f"http://127.0.0.1:{first.server_port}"
    try:
        async with BrowserSession(False) as browser:
            await browser.active.goto(first_url + "/home")
            executor = ActionExecutor(browser, [first_url])
            assert (await executor.execute(action("goto_url", url=first_url + "/redirect"))).ok
            assert browser.active.url == second_url + "/final"
            assert (await executor.execute(action("back"))).ok
            assert browser.active.url == first_url + "/home"
            assert (await executor.execute(action("forward"))).ok
            assert browser.active.url == second_url + "/final"
            assert (await executor.execute(action("refresh"))).ok

            assert (await executor.execute(action("new_tab", url=second_url + "/new"))).ok
            assert browser.active.url == second_url + "/new"
            assert len([page for page in browser.pages if not page.is_closed()]) == 2
            assert (await executor.execute(action("switch_tab", target_tab_id="tab-1"))).ok
            assert browser.active.url == second_url + "/final"
            assert (await executor.execute(action("close_tab", target_tab_id="tab-2"))).ok
            assert len([page for page in browser.pages if not page.is_closed()]) == 1

        async with BrowserSession(False) as browser:
            await browser.active.goto(first_url + "/home")
            await install_scenario_origin_guard(browser, [first_url])
            guarded = await ActionExecutor(browser, [first_url]).execute(
                action("goto_url", url=second_url + "/final")
            )
            assert not guarded.ok
            assert browser.active.url.startswith(first_url)
    finally:
        first.shutdown()
        second.shutdown()
        first.server_close()
        second.server_close()


class _PageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        status, body = self.server.callback(self.path)
        self.send_response(status)
        if status == 302:
            self.send_header("Location", body)
        else:
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if status != 302:
            self.wfile.write(body.encode())

    def log_message(self, *_args):
        pass


@pytest.mark.asyncio
async def test_tool_errors_remain_errors_without_becoming_authorization_errors():
    async with BrowserSession(False) as browser:
        await _start(browser, "<p>page</p>")
        executor = ActionExecutor(browser, ["https://elsewhere.test"])
        missing = await executor.execute(action("click", target_id="not-present"))
        assert not missing.ok and missing.error["code"] == "target_not_found"
        invalid_tab = await executor.execute(action("switch_tab", target_tab_id="tab-99"))
        assert not invalid_tab.ok and invalid_tab.error["code"] == "target_not_found"
