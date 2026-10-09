import json
import re
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

from uxagent.monitor import Dashboard, make_handler

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def local_dashboard(tmp_path, monkeypatch):
    dashboard=Dashboard(tmp_path/"runs",tmp_path/"personas",ROOT/"configs/study.json")
    monkeypatch.setattr(dashboard,"_verify_connection",lambda provider:None)
    for i in range(2):
        run=dashboard.runs_dir/f"run-{i}"
        run.mkdir(parents=True)
        (run/"run.json").write_text(json.dumps({"run_id":run.name,"started_at":f"2026-10-09T00:00:0{i}"}),encoding="utf-8")
        (run/"persona.json").write_text((ROOT/"configs/persona.json").read_text(encoding="utf-8"),encoding="utf-8")
        (run/"summary.json").write_text('{"verification":"success","termination_reason":"verified_success"}',encoding="utf-8")
    experiment=dashboard.runs_dir/"experiments"/"e1"
    experiment.mkdir(parents=True)
    (experiment/"experiment.json").write_text(json.dumps({"experiment_id":"e1","sessions":[
        {"condition":"general","pair_persona_id":"p1","repetition":1,"run_id":"planned-only","status":"not_started","verification":"unknown"},
        {"condition":"persona","pair_persona_id":"p1","repetition":1,"run_id":"run-0","status":"completed","verification":"success"}
    ]}),encoding="utf-8")
    server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(dashboard))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown();server.server_close();thread.join(timeout=3)


def test_tabs_preserve_form_and_run_selection_during_polling(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto(local_dashboard)
        expect(page.locator("#connection")).to_have_text("연결됨")
        page.locator("#task-input").fill("입력 중인 과업")
        page.get_by_role("tab",name="AI 비교",exact=True).click()
        expect(page.locator("#view-compare")).to_be_visible()
        page.get_by_role("tab",name="실행 기록",exact=True).click()
        page.locator("#run-select").select_option("run-0")
        page.wait_for_timeout(2200)
        expect(page.locator("#run-select")).to_have_value("run-0")
        page.get_by_role("tab",name="과업 테스트",exact=True).click()
        expect(page.locator("#task-input")).to_have_value("입력 중인 과업")
        assert errors == []
        browser.close()


def test_key_explicit_connection_is_cleared_and_never_browser_stored(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.goto(local_dashboard)
        page.locator("#connection-provider").select_option("live")
        page.locator("#api-key").fill("test-ui-credential")
        page.get_by_role("button",name="API 연결",exact=True).click()
        expect(page.locator("#api-key")).to_have_value("")
        assert page.evaluate("localStorage.length + sessionStorage.length") == 0
        assert "test-ui-credential" not in page.request.get(local_dashboard+"/api/state").text()
        assert page.request.post(local_dashboard+"/api/connection",data={"provider":"live","api_key":"test-other"},headers={"Origin":"https://evil.test"}).status == 403
        browser.close()


def test_mobile_layout_has_no_horizontal_overflow(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={"width":390,"height":844})
        page.goto(local_dashboard)
        expect(page.locator("#view-test")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_role("tab",name="개선 보드",exact=True).click()
        expect(page.locator("#view-board")).to_be_visible()
        browser.close()


def test_unstarted_session_does_not_link_to_nonexistent_run(local_dashboard):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page()
        page.goto(local_dashboard)
        page.get_by_role("tab",name="AI 비교",exact=True).click()
        expect(page.locator("#experiments").get_by_role("button",name=re.compile("미확인.*미실행"))).to_be_disabled()
        assert page.locator('#experiments [data-run="planned-only"]').count()==0
        page.locator('#experiments [data-run="run-0"]').first.click()
        expect(page.locator("#view-history")).to_be_visible()
        expect(page.locator("#run-select")).to_have_value("run-0")
        browser.close()
