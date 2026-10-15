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


@pytest.mark.parametrize('status,error', [(400,'invalid_review_input'), (404,'card_not_found'), (409,'card_version_conflict'), (500,'review_history_unavailable')])
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


def test_changed_evidence_requires_reload_before_new_review(review_dashboard, tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        old = page.request.get(review_dashboard + '/api/run/review-run').json()
        page.route('**/api/run/review-run', lambda route: route.fulfill(json=old))
        form = open_form(page, review_dashboard)
        fill_form(form)
        summary_path = tmp_path / 'runs' / 'review-run' / 'summary.json'
        summary = json.loads(summary_path.read_text())
        summary['evaluator']['feature_checks'][0]['reason'] = '변경된 근거'
        summary_path.write_text(json.dumps(summary))
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(form.get_by_role('status')).to_contain_text('근거가 변경')
        expect(form.get_by_role('button', name='판정 저장', exact=True)).to_be_disabled()
        page.unroute('**/api/run/review-run')
        form.get_by_role('button', name='근거 다시 확인').click()
        expect(page.locator('#view-history')).to_be_visible()
        page.locator('#tab-board').click()
        expect(form.get_by_label('검토 메모')).to_have_value('')
        fill_form(form, 'deferred')
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(form.get_by_role('status')).to_contain_text('저장했습니다')
        result = page.request.get(review_dashboard + '/api/reviews/review-run').json()
        assert len(result['reviews']) == 1
        assert result['reviews'][0]['card_version'] != old['cards'][0]['card_version']
        browser.close()


def test_review_form_small_screen_and_empty_verdict(review_dashboard, tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width':390, 'height':844})
        form = open_form(page, review_dashboard)
        form.get_by_label('검토자 별칭').fill('test-reviewer')
        form.get_by_role('button', name='판정 저장', exact=True).click()
        assert page.request.get(review_dashboard + '/api/reviews/review-run').json()['reviews'] == []
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(tmp_path / 'review-mobile.png'), full_page=True)
        page.set_viewport_size({'width':1365, 'height':900})
        page.screenshot(path=str(tmp_path / 'review-desktop.png'), full_page=True)
        browser.close()


# D-02: use identical candidate IDs across runs to detect draft cross-contamination.
def add_review_run(tmp_path, run_id):
    folder = tmp_path / 'runs' / run_id
    folder.mkdir(exist_ok=True)
    (folder / 'run.json').write_text(json.dumps({'run_id': run_id, 'execution_mode': 'scripted'}))
    (folder / 'summary.json').write_text(json.dumps({'verification': 'failure', 'evaluator': {'feature_checks': [
        {'id': '검색/a', 'label': '검색 결과', 'status': 'fail', 'reason': '결과 없음'},
        {'id': '가격', 'label': '가격 조건', 'status': 'fail', 'reason': '가격 불일치'}]}}))


def select_review_run(page, run_id):
    page.locator('#tab-history').click()
    page.locator('#run-select').select_option(run_id)
    page.locator('#tab-board').click()
    expect(page.locator('#board-run-label')).to_contain_text(run_id)
    expect(page.locator('.review-form')).to_have_count(2)


def test_drafts_survive_polling_and_round_trip_between_runs(review_dashboard, tmp_path):
    add_review_run(tmp_path, 'review-run')
    add_review_run(tmp_path, 'other-run')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        open_form(page, review_dashboard)
        select_review_run(page, 'review-run')
        first, second = page.locator('.review-form').nth(0), page.locator('.review-form').nth(1)
        fill_form(first, 'deferred')
        second.get_by_label('검토 메모').fill('두 번째 카드 초안')
        note = first.get_by_label('검토 메모')
        note.focus()
        note.press('Home')
        note.press('Shift+ArrowRight')
        selection = note.evaluate('(e)=>[e.selectionStart,e.selectionEnd]')
        for _ in range(2):
            with page.expect_response(lambda r: '/api/run/review-run' in r.url):
                pass
        expect(note).to_be_focused()
        assert note.evaluate('(e)=>[e.selectionStart,e.selectionEnd]') == selection
        select_review_run(page, 'other-run')
        expect(first.get_by_label('검토 메모')).to_have_value('')
        fill_form(first, 'invalid')
        first.get_by_label('검토 메모').fill('다른 실행 초안')
        select_review_run(page, 'review-run')
        expect(first.get_by_label('판정', exact=True)).to_have_value('deferred')
        expect(first.get_by_label('검토 메모')).to_have_value('근거 확인 <b>테스트</b>')
        expect(second.get_by_label('검토 메모')).to_have_value('두 번째 카드 초안')
        first.get_by_role('button', name='판정 저장', exact=True).click()
        expect(first.get_by_role('status')).to_contain_text('저장했습니다')
        assert page.request.get(review_dashboard+'/api/reviews/other-run').json()['reviews'] == []
        select_review_run(page, 'other-run')
        expect(first.get_by_label('검토 메모')).to_have_value('다른 실행 초안')
        assert page.evaluate('localStorage.length+sessionStorage.length') == 0
        browser.close()


def test_late_poll_cannot_undo_confirmed_review(review_dashboard):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        form = open_form(page, review_dashboard)
        fill_form(form)
        old = page.request.get(review_dashboard+'/api/run/review-run').json()
        held = []
        page.route('**/api/run/review-run', lambda route: held.append(route))
        with page.expect_request(lambda r: '/api/run/review-run' in r.url):
            pass
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(form.get_by_role('status')).to_contain_text('저장했습니다')
        with page.expect_request(lambda r: '/api/run/review-run' in r.url):
            held[0].fulfill(json=old)
        expect(page.locator('#cards .badge')).to_have_text('유효 후보')
        browser.close()


@pytest.mark.parametrize('outcome', ['success', 'failure'])
def test_delayed_save_stays_with_original_run_and_retry(review_dashboard, tmp_path, outcome):
    add_review_run(tmp_path, 'review-run')
    add_review_run(tmp_path, 'other-run')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        open_form(page, review_dashboard)
        select_review_run(page, 'review-run')
        form = page.locator('.review-form').first
        fill_form(form)
        held = []
        page.route('**/api/reviews/review-run', lambda route: held.append(route))
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(form.get_by_role('button', name='저장 중')).to_be_disabled()
        select_review_run(page, 'other-run')
        form.get_by_label('검토 메모').fill('현재 실행 초안')
        if outcome == 'success':
            response = page.request.post(review_dashboard+'/api/reviews/review-run', data=held[0].request.post_data_json)
            held[0].fulfill(status=response.status, json=response.json())
        else:
            held[0].fulfill(status=500, json={'error':'review_history_unavailable'})
        expect(form.get_by_label('검토 메모')).to_have_value('현재 실행 초안')
        expect(page.locator('#cards .badge').first).to_have_text('사람 검토 전')
        select_review_run(page, 'review-run')
        expect(form.get_by_label('검토 메모')).to_have_value('근거 확인 <b>테스트</b>')
        if outcome == 'failure':
            expect(form.get_by_role('status')).to_contain_text('저장하지 못했습니다')
            page.unroute('**/api/reviews/review-run')
            form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(form.get_by_role('status')).to_contain_text('저장했습니다')
        assert len(page.request.get(review_dashboard+'/api/reviews/review-run').json()['reviews']) == 1
        assert page.request.get(review_dashboard+'/api/reviews/other-run').json()['reviews'] == []
        browser.close()


@pytest.mark.parametrize('field', ['검토자 별칭', '검토 메모'])
def test_poll_rerender_preserves_focused_selection(review_dashboard, field):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        form = open_form(page, review_dashboard)
        fill_form(form)
        control = form.get_by_label(field)
        control.focus()
        control.press('Home')
        control.press('Shift+ArrowRight')
        control.press('Shift+ArrowRight')
        selection = control.evaluate('(e)=>[e.selectionStart,e.selectionEnd]')
        card = page.request.get(review_dashboard+'/api/reviews/review-run').json()['cards'][0]
        response = page.request.post(review_dashboard+'/api/reviews/review-run', data={
            'card_id':card['card_id'],'card_version':card['card_version'],
            'reviewer_id':'another-test-reviewer','verdict':'deferred','note':'외부 저장으로 카드 갱신'})
        assert response.status == 201
        expect(page.locator('#cards .badge')).to_have_text('판단 보류')
        expect(control).to_be_focused()
        assert control.evaluate('(e)=>[e.selectionStart,e.selectionEnd]') == selection
        expect(form.get_by_label('검토 메모')).to_have_value('근거 확인 <b>테스트</b>')
        expect(form.get_by_label('판정', exact=True)).to_have_value('valid')
        browser.close()


def test_round_trip_ignores_inflight_detail_from_previous_selection(review_dashboard, tmp_path):
    add_review_run(tmp_path, 'review-run')
    add_review_run(tmp_path, 'other-run')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        open_form(page, review_dashboard)
        select_review_run(page, 'review-run')
        fill_form(page.locator('.review-form').first)
        old = page.request.get(review_dashboard+'/api/run/review-run').json()
        held = []
        page.route('**/api/run/review-run', lambda route: held.append(route))
        with page.expect_request(lambda r: '/api/run/review-run' in r.url):
            pass
        page.locator('#tab-history').click()
        page.locator('#run-select').select_option('other-run')
        page.locator('#run-select').select_option('review-run')
        with page.expect_request(lambda r: '/api/run/review-run' in r.url):
            held[0].fulfill(json=old)
        # No stale form may be mounted until the newly selected run is fetched.
        expect(page.locator('.review-form')).to_have_count(0)
        held[1].continue_()
        page.unroute('**/api/run/review-run')
        page.locator('#tab-board').click()
        expect(page.locator('.review-form').first.get_by_label('검토 메모')).to_have_value('근거 확인 <b>테스트</b>')
        browser.close()


def test_history_versions_save_reload_and_expansion(review_dashboard, tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width':390, 'height':844})
        form = open_form(page, review_dashboard)
        history = page.locator('.review-history')
        history.locator('summary').click()
        expect(history).to_contain_text('현재 버전의 저장된 검토가 없습니다')
        fill_form(form, 'deferred')
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(history.locator('.review-record')).to_have_count(1)
        expect(history).to_have_attribute('open', '')
        expect(history.locator('time')).to_have_attribute('datetime', __import__('re').compile(r'^20'))
        expect(history).to_contain_text('근거 확인 <b>테스트</b>')
        assert history.locator('b').count() == 0
        fill_form(form, 'valid')
        form.get_by_role('button', name='판정 저장', exact=True).click()
        expect(history.locator('.review-record')).to_have_count(2)
        expect(history).to_have_attribute('open', '')
        page.reload()
        page.locator('#tab-board').click()
        history.locator('summary').click()
        expect(history.locator('.review-record')).to_have_count(2)
        path = tmp_path / 'runs/review-run/summary.json'
        summary = json.loads(path.read_text())
        summary['evaluator']['feature_checks'][0]['reason'] = '새 근거'
        path.write_text(json.dumps(summary))
        expect(page.locator('#cards .badge')).to_have_text('사람 검토 전')
        expect(history).to_contain_text('이전 버전 검토 (2건)')
        expect(history).to_contain_text('현재 버전의 저장된 검토가 없습니다')
        history.locator('summary').click()
        expect(history.locator('.review-record')).to_have_count(2)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        assert page.request.get(review_dashboard+'/api/run/review-run').json()['summary']['verification'] == 'failure'
        browser.close()


@pytest.mark.parametrize('metadata,execution,source', [
    ({'execution_mode':'scripted','source_kind':'synthetic_fixture'}, '사전 정의 스크립트', '합성 테스트 환경'),
    ({'execution_mode':'ai','source_kind':'live_configured'}, 'AI 실행', '실제 사이트'),
    ({'provider':'mock','execution_mode':'ai'}, 'Mock 데모', '미확인'),
    ({'provider':'gemini','start_url':'https://example.com'}, '미확인', '미확인'),
])
def test_provenance_axes_and_legacy_no_inference(review_dashboard, tmp_path, metadata, execution, source):
    path = tmp_path / 'runs/review-run/run.json'
    path.write_text(json.dumps({'run_id':'review-run', **metadata}))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(review_dashboard)
        page.locator('#tab-history').click()
        expect(page.locator('#run-provenance')).to_contain_text('실행 방식: '+execution)
        expect(page.locator('#run-provenance')).to_contain_text('대상 출처: '+source)
        page.locator('#tab-board').click()
        expect(page.locator('#board-provenance')).to_contain_text('실행 방식: '+execution)
        expect(page.locator('#board-provenance')).to_contain_text('실제 사람의 행동·판단 데이터가 아닙니다')
        browser.close()
