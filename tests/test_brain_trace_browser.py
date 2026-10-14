import json
import threading
from http.server import ThreadingHTTPServer
import pytest
from playwright.sync_api import sync_playwright, expect
from uxagent.monitor import Dashboard, make_handler
from test_brain_trace import brain_folder
from test_review_export_browser import download_reports


@pytest.fixture
def trace_dashboard(brain_folder):
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Dashboard(brain_folder.parent)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try: yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown();server.server_close();thread.join()


def test_brain_states_and_evicted_sources_match_downloads(trace_dashboard,tmp_path):
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(accept_downloads=True,viewport={'width':390,'height':844})
        page.goto(trace_dashboard)
        page.locator('#tab-history').click()
        page.locator('#brain-trace > summary').click()
        expect(page.locator('#brain-content')).to_contain_text('실행된 행동·독립 평가·사람 검토와 별개')
        for label in ('예약 1','진행 1','완료 1','생략 1','실패 1','취소 1'):
            expect(page.locator('#brain-content')).to_contain_text(label)
        expect(page.locator('#brain-content script')).to_have_count(0)
        page.locator('[data-brain-key="memory:m1"] summary').click()
        expect(page.locator('#brain-content')).to_contain_text('원본 관찰')
        expect(page.locator('[data-brain-key="memory:m1"]')).to_contain_text('obs-memory-source')
        expect(page.locator('#brain-content')).to_contain_text('활성 목록에서 제거됨')
        expect(page.locator('#brain-content')).to_contain_text('9 / 1–10')
        reports=download_reports(page,tmp_path)
        trace=json.loads(reports['json'])['brain']
        assert trace['task_counts']['completed']==1
        for kind in ('csv','md','html'): assert 'stage1' in reports[kind]
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()


def test_stage_opens_exact_source_observation(trace_dashboard,brain_folder):
    import base64
    obs=brain_folder/'observations';obs.mkdir()
    (obs/'obs-source.json').write_text(json.dumps({'observation_id':'obs-source','url':'http://example.test/source','title':'source'}))
    (obs/'obs-source.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aFOkAAAAASUVORK5CYII='))
    path=brain_folder/'brain_stages.jsonl'
    stage=json.loads(path.read_text().splitlines()[0]);stage['observation_id']='obs-source'
    path.write_text(''.join(json.dumps({**stage,'record_id':'earlier-'+str(i)})+'\n' for i in range(30))+json.dumps(stage)+'\n')
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page()
        page.goto(trace_dashboard);page.locator('#tab-history').click()
        page.locator('#brain-trace > summary').click()
        page.locator('[data-brain-key="stage:stage1"] summary').click()
        page.get_by_role('button',name='관찰 obs-source 보기',exact=True).click()
        expect(page.locator('#shot-caption')).to_have_text('선택 관찰 · obs-source')
        expect(page.locator('#shot-caption')).to_be_in_viewport()
        expect(page.locator('#shot-wrap img')).to_have_attribute('src','/artifacts/brain-demo/observations/obs-source.png')
        page.get_by_role('button',name='최근 화면',exact=True).click()
        expect(page.locator('#shot-caption')).to_have_text('최근 관찰 · obs-source')
        browser.close()
