"""D-04 display contracts against the real aggregate/HTTP path (synthetic data)."""
import json
import threading
from http.server import ThreadingHTTPServer

import pytest
from playwright.sync_api import sync_playwright, expect
from uxagent.monitor import Dashboard, make_handler


def write_comparison_fixture(root):
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, (status, result) in enumerate([
        ('completed', 'success'), ('completed', 'success'), ('error', 'failure'),
        ('cancelled', 'unknown'), ('not_started', 'unknown')]):
        row = dict(condition='general', pair_persona_id=f'p{index}', repetition=1,
                   status=status, verification=result, run_id='evidence-run' if index==0 else f'missing-{index}')
        if index == 0:
            row.update(action_attempts=6, elapsed_ms=2000, cost=0, llm_tokens=0, llm_request_count=0,
                       provider_usage={}, metrics={'recording':{'attempted':4,'complete':3}})
        if index == 1:
            row.update(cost_complete=False, cost_measured_total=.125,
                       llm_tokens_complete=False, llm_tokens_measured_total=120,
                       provider_usage={'mock':{'input_tokens_complete':False,'input_tokens_measured_total':100,
                                              'output_tokens':20}})
        rows.append(row)
    rows.append(dict(condition='persona',pair_persona_id='p0',repetition=1,status='completed',
                     verification='failure',cost=0,llm_tokens=0,llm_request_count=0,provider_usage={},
                     metrics={'recording':{'attempted':0,'complete':0}}))
    experiment = dict(experiment_id='D04-synthetic-display-fixture', started_at='2026-10-14T12:00:00Z',
        settings={'provider':'mock','repetitions':1,'prompt_version':'fast-2', 'study':{
            'task':'[가상 표시 검증] 검색·필터 조건 확인', 'start_url':'https://example.com',
            'provider_model':'fixture-model', 'viewport':{'width':1440,'height':900},
            'observation_policy':'viewport'}}, sessions=rows)
    (root/'experiment.json').write_text(json.dumps(experiment), encoding='utf-8')
    run = root/'evidence-run'
    run.mkdir(exist_ok=True)
    (run/'run.json').write_text(json.dumps({'run_id':'evidence-run','provider':'mock'}))
    (run/'summary.json').write_text(json.dumps({'verification':'success'}))
    return experiment


@pytest.fixture
def comparison_dashboard(tmp_path):
    root = tmp_path/'runs'
    write_comparison_fixture(root)
    server = ThreadingHTTPServer(('127.0.0.1',0), make_handler(Dashboard(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    server.server_close()
    thread.join()


def open_comparison(page, url):
    page.goto(url)
    page.get_by_role('tab', name='AI 비교', exact=True).click()
    return page.locator('#experiments')


def test_comparison_partial_coverage_and_evidence(comparison_dashboard):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        panel = open_comparison(page, comparison_dashboard)
        row = panel.locator('.comparison-results tbody tr').first
        expect(row).to_contain_text('2 / 5')
        expect(row).to_contain_text('40.0%')
        expect(row).to_contain_text('성공 2 · 실패 1 · 미확인 2')
        expect(row).to_contain_text('취소 1')
        expect(row).to_contain_text('미실행 1')
        expect(row).to_contain_text('계산 대상 1 / 성공 2회')
        cost = panel.locator('[data-condition="general"] [data-measure="cost"]')
        expect(cost).to_contain_text('전체: 미확인')
        expect(cost).to_contain_text('측정 부분값: $0.12500')
        expect(cost).to_contain_text('완전 측정 1 / 예정 5회 · 누락 포함 4회')
        tokens = panel.locator('[data-condition="general"] [data-measure="llm_tokens"]')
        expect(tokens).to_contain_text('측정 부분값: 120')
        recording = panel.locator('[data-condition="general"] [data-measure="recording"]')
        expect(recording).to_contain_text('전체: 미확인')
        expect(recording).to_contain_text('측정 범위: 3 / 4행동 · 75.0%')
        expect(panel.locator('[data-condition="persona"] [data-measure="cost"]')).to_contain_text('전체: $0.00000')
        expect(panel.locator('[data-condition="persona"] [data-measure="recording"]')).to_contain_text('대상 행동 없음')
        panel.locator('summary').filter(has_text='실험 조건과 측정 상세').click()
        expect(panel).to_contain_text('fixture-model')
        expect(panel).to_contain_text('1440 × 900')
        expect(panel).to_contain_text('환경 식별자: 미기록')
        expect(panel.get_by_role('button',name='미확인 미실행')).to_be_disabled()
        assert panel.locator('[data-run="missing-4"]').count() == 0
        panel.locator('button[data-run="evidence-run"]').click()
        expect(page.locator('#view-history')).to_be_visible()
        browser.close()


def test_zero_empty_and_legacy_measurement(comparison_dashboard, tmp_path):
    path = tmp_path/'runs/experiment.json'
    fixture = json.loads(path.read_text())
    fixture['settings'] = {}
    fixture['sessions'] = [dict(condition='general',status='cancelled',verification='unknown')]
    path.write_text(json.dumps(fixture))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width':390,'height':844})
        panel = open_comparison(page, comparison_dashboard)
        rows = panel.locator('.comparison-results tbody tr')
        expect(rows.nth(0)).to_contain_text('0 / 1')
        expect(rows.nth(0)).to_contain_text('0.0%')
        expect(rows.nth(1)).to_contain_text('0 / 0')
        expect(rows.nth(1)).to_contain_text('예정 세션 없음')
        expect(panel.locator('[data-condition="general"] [data-measure="cost"]')).to_contain_text('측정 부분값: 미확인')
        panel.locator('summary').filter(has_text='실험 조건과 측정 상세').click()
        expect(panel).to_contain_text('모델 설정: 미기록')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()


def test_comparison_expansion_survives_poll(comparison_dashboard, tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        panel = open_comparison(page, comparison_dashboard)
        panel.locator('summary').filter(has_text='실험 조건과 측정 상세').click()
        path = tmp_path/'runs/experiment.json'
        experiment = json.loads(path.read_text())
        experiment['sessions'][1]['cost_measured_total'] = .25
        path.write_text(json.dumps(experiment))
        expect(panel.locator('[data-condition="general"] [data-measure="cost"]')).to_contain_text('$0.25000')
        for _ in range(2):
            with page.expect_response(lambda r: '/api/experiments' in r.url):
                pass
        expect(panel.locator('.comparison-details')).to_have_attribute('open','')
        browser.close()


def test_partial_zero_is_not_unknown_and_scripted_excluded(comparison_dashboard, tmp_path):
    path = tmp_path/'runs/experiment.json'
    data = json.loads(path.read_text())
    data['sessions'] = [
        dict(condition='general',status='error',verification='unknown',cost_complete=False,cost_measured_total=0),
        dict(condition='general',status='completed',verification='success',execution_mode='scripted',pair_persona_id='excluded-script')]
    path.write_text(json.dumps(data))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        panel = open_comparison(page, comparison_dashboard)
        expect(panel.locator('.comparison-results tbody tr').first).to_contain_text('0 / 1')
        cost = panel.locator('[data-condition="general"] [data-measure="cost"]')
        expect(cost).to_contain_text('전체: 미확인')
        expect(cost).to_contain_text('측정 부분값: $0.00000')
        expect(cost).to_contain_text('완전 측정 0 / 예정 1회 · 누락 포함 1회')
        expect(panel).not_to_contain_text('excluded-script')
        browser.close()


def test_empty_comparison_list(comparison_dashboard, tmp_path):
    (tmp_path/'runs/experiment.json').unlink()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        panel = open_comparison(page, comparison_dashboard)
        expect(panel).to_contain_text('비교 기록이 없습니다')
        browser.close()
