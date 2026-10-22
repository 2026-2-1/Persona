"""D consumer integration with final U observations and simulated survey records."""
import csv
import io
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

import pytest
from playwright.sync_api import sync_playwright, expect

from uxagent.monitor import Dashboard, make_handler
from test_u_result_views import u_folder, completed_survey, put
from test_review_form_browser import fill_form
from test_review_export_browser import download_reports


@pytest.fixture
def u_dashboard(u_folder):
    completed_survey(u_folder)
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Dashboard(u_folder.parent)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_exports_have_attachment_headers_for_all_browsers(u_dashboard):
    for kind in ('json', 'csv', 'md', 'html'):
        with urlopen(u_dashboard+'/api/export/u-review?format='+kind) as response:
            assert response.headers.get('Content-Disposition') == f'attachment; filename="u-review.{kind}"'


def test_u_evidence_review_reload_and_all_downloads(u_dashboard, tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(accept_downloads=True, viewport={'width':390,'height':844})
        page.goto(u_dashboard)
        page.locator('#tab-history').click()
        expect(page.locator('#final-evaluation')).to_contain_text('실패 확인')
        expect(page.locator('#final-evaluation')).to_contain_text('agent_finished')
        page.locator('#survey-panel > summary').click()
        expect(page.locator('#survey-panel')).to_contain_text('AI가 생성한 자기보고')
        expect(page.locator('#survey-panel')).to_contain_text('합성 설문 답변')
        page.locator('#brain-trace > summary').click()
        page.locator('[data-brain-key="wonder"] > summary').click()
        wonder = page.locator('[data-brain-key="wonder"]')
        expect(wonder).to_contain_text('생각 2개')
        expect(wonder).to_contain_text('빈 응답 1회')
        expect(wonder).not_to_contain_text('1%')
        expect(wonder).to_contain_text('합성 생각 A · 기억 저장: 예')
        expect(wonder).to_contain_text('합성 생각 B · 기억 저장: 아니요')
        page.locator('#tab-board').click()
        page.get_by_role('button', name='최종 평가 근거 보기', exact=True).click()
        expect(page.locator('#shot-caption')).to_have_text('선택 관찰 · obs-final')
        expect(page.locator('#view-history')).to_be_visible()
        page.locator('#tab-board').click()
        form = page.locator('.review-form').first
        fill_form(form, 'deferred')
        form.get_by_label('검토 메모').fill('U 합성 자료의 저장·출력 검증')
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(form.get_by_role('status')).to_contain_text('저장했습니다')
        page.reload()
        page.locator('#tab-board').click()
        expect(page.locator('#cards .badge')).to_have_text('판단 보류')
        card = page.request.get(u_dashboard+'/api/run/u-review').json()['cards'][0]
        reports = download_reports(page, tmp_path)
        payload = json.loads(reports['json'])
        assert payload['cards'][0] == card
        assert payload['summary']['verification'] == 'failure'
        assert payload['final_evaluation']['observation_id'] == 'obs-final'
        assert payload['survey']['answers'][0]['answer'] == '합성 설문 답변'
        assert payload['wonder']['empty_responses'] == 1
        csv_rows = list(csv.DictReader(io.StringIO(reports['csv'])))
        candidate = next(row for row in csv_rows if row['record_type']=='candidate')
        for key in ('card_id','card_version','verdict','note','reviewer_id'):
            assert candidate[key] == card[key]
        assert candidate['observation_id'] == 'obs-final'
        for kind, text in reports.items():
            assert '합성 설문 답변' in text and 'obs-final' in text
            assert 'LOCAL_RESPONSE_ONLY' not in text and 'LOCAL_REQUEST_ONLY' not in text
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()


def test_failed_survey_refresh_drops_stale_success(u_dashboard, u_folder):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(u_dashboard)
        page.locator('#tab-history').click()
        page.locator('#survey-panel > summary').click()
        expect(page.locator('#survey-panel')).to_contain_text('합성 설문 답변')
        put(u_folder, 'survey_result.json', {'status':'invalid_json','error':{'code':'invalid_json'}})
        expect(page.locator('#survey-panel')).to_contain_text('invalid_json')
        expect(page.locator('#survey-panel')).not_to_contain_text('합성 설문 답변')
        assert page.locator('#survey-panel').get_attribute('open') is not None
        browser.close()
