"""D-01: browser form against the real local review API; no paid model calls."""
import json
import threading
from http.server import ThreadingHTTPServer

import pytest
from playwright.sync_api import sync_playwright, expect
from uxagent.monitor import Dashboard, make_handler


@pytest.fixture
def review_dashboard(tmp_path):
    run = tmp_path / 'runs' / 'review-run'
    run.mkdir(parents=True)
    (run / 'run.json').write_text(json.dumps({'run_id': 'review-run', 'execution_mode': 'scripted', 'source_kind': 'synthetic_fixture'}))
    (run / 'summary.json').write_text(json.dumps({'verification': 'failure', 'evaluator': {'feature_checks': [
        {'id': '검색/a', 'label': '검색 결과', 'status': 'fail', 'reason': '결과 없음'}]}}))
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Dashboard(tmp_path / 'runs')))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def open_form(page, url):
    page.goto(url)
    page.locator('#tab-board').click()
    form = page.locator('.review-form').first
    expect(form).to_be_visible()
    return form


def fill_form(form, verdict='valid'):
    form.get_by_label('검토자 별칭').fill('test-reviewer')
    form.get_by_label('판정', exact=True).select_option(verdict)
    form.get_by_label('검토 메모').fill('근거 확인 <b>테스트</b>')


@pytest.mark.parametrize('verdict,label', [('valid','유효 후보'), ('invalid','무효 후보'), ('deferred','판단 보류'), ('tool_error','도구 오류'), ('environment_error','환경 오류')])
def test_review_form_saves_real_api_and_survives_reload(review_dashboard, verdict, label):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        form = open_form(page, review_dashboard)
        fill_form(form, verdict)
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(form.get_by_role('status')).to_contain_text('저장했습니다')
        stored = page.request.get(review_dashboard + '/api/reviews/review-run').json()
        assert len(stored['reviews']) == 1
        assert stored['reviews'][0]['verdict'] == verdict
        page.reload()
        page.locator('#tab-board').click()
        expect(page.locator('#cards .badge')).to_have_text(label)
        expect(page.locator('#cards')).to_contain_text('근거 확인 <b>테스트</b>')
        assert page.locator('#cards b').count() == 0
        detail = page.request.get(review_dashboard + '/api/run/review-run').json()
        assert detail['summary']['verification'] == 'failure'
        assert page.evaluate('localStorage.length + sessionStorage.length') == 0
        browser.close()


@pytest.mark.parametrize('status,error', [(400,'invalid_review_input'), (404,'card_not_found'), (409,'card_version_mismatch'), (500,'review_history_unavailable')])
def test_review_form_failure_keeps_input_and_does_not_claim_saved(review_dashboard, status, error):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route('**/api/reviews/review-run', lambda route: route.fulfill(status=status, json={'error': error}))
        form = open_form(page, review_dashboard)
        fill_form(form)
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(form.get_by_role('status')).not_to_be_empty()
        expect(form.get_by_role('status')).not_to_contain_text('저장했습니다')
        expect(form.get_by_label('검토 메모')).to_have_value('근거 확인 <b>테스트</b>')
        if status == 409:
            expect(form.get_by_role('button', name='판정 저장', exact=True)).to_be_disabled()
            expect(form.get_by_role('button', name='근거 다시 확인')).to_be_visible()
        assert page.request.get(review_dashboard + '/api/reviews/review-run').json()['reviews'] == []
        browser.close()


def test_review_form_pending_disables_duplicate_save_and_validates_alias(review_dashboard):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        pending = []
        page.route('**/api/reviews/review-run', lambda route: pending.append(route))
        form = open_form(page, review_dashboard)
        fill_form(form)
        form.get_by_label('검토자 별칭').fill('   ')
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(form.get_by_role('status')).to_contain_text('별칭')
        assert pending == []
        form.get_by_label('검토자 별칭').fill('test-reviewer')
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(form.get_by_role('button', name='저장 중')).to_be_disabled()
        expect(form.get_by_label('검토 메모')).to_be_disabled()
        page.wait_for_timeout(1700)
        assert len(pending) == 1
        pending[0].fulfill(status=500, json={'error':'review_history_unavailable'})
        expect(form.get_by_role('button', name='판정 저장', exact=True)).to_be_enabled()
        expect(form.get_by_label('검토 메모')).to_have_value('근거 확인 <b>테스트</b>')
        browser.close()
