"""D-05: real HTTP save, reload and browser downloads of the same candidate."""
import csv
import io
import json
from html import unescape

import pytest
from playwright.sync_api import sync_playwright, expect
from test_review_form_browser import review_dashboard, open_form, fill_form


def download_reports(page, folder):
    page.locator('#tab-history').click()
    page.get_by_text('자료 내보내기', exact=True).click()
    reports = {}
    for kind in ('json','csv','md','html'):
        with page.expect_download() as download:
            page.locator(f'#exports a[href$="format={kind}"]').click()
        path = folder / f'report.{kind}'
        download.value.save_as(path)
        reports[kind] = path.read_text(encoding='utf-8')
    return reports


@pytest.mark.parametrize('verdict,label', [('valid','유효 후보'),('deferred','판단 보류')])
def test_saved_review_matches_all_downloads_after_reload(review_dashboard, tmp_path, verdict, label):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(accept_downloads=True, viewport={'width':390,'height':844})
        form = open_form(page, review_dashboard)
        fill_form(form, verdict)
        note = 'D05 가상 검토: 쉼표, "따옴표"\n두 번째 줄 <b>텍스트</b>'
        form.get_by_label('검토 메모').fill(note)
        form.get_by_role('button',name='판정 저장',exact=True).click()
        expect(form.get_by_role('status')).to_contain_text('저장했습니다')
        page.reload()
        page.locator('#tab-board').click()
        expect(page.locator('#cards .badge')).to_have_text(label)
        page.locator('.review-history summary').click()
        expect(page.locator('.review-record .review-note')).to_have_text(note)
        card = page.request.get(review_dashboard+'/api/run/review-run').json()['cards'][0]
        expect(page.locator('.review-version')).to_contain_text(card['card_version'])
        reports = download_reports(page, tmp_path)
        payload = json.loads(reports['json'])
        assert payload['summary']['verification'] == 'failure'
        assert payload['cards'][0] == card
        row = next(csv.DictReader(io.StringIO(reports['csv'])))
        for key in ('run_id','card_id','card_version','verdict','note','reviewer_id','review_status'):
            assert row[key] == card[key]
        for kind in ('md','html'):
            text = unescape(reports[kind]) if kind == 'html' else reports[kind]
            for value in (card['card_id'],card['card_version'],note,card['reviewer_id']):
                assert value in text
            assert '판정: '+verdict in text
        assert '<b>텍스트</b>' not in reports['html']
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()


def test_changed_evidence_exports_current_identity_without_old_verdict(review_dashboard, tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(accept_downloads=True)
        form = open_form(page, review_dashboard)
        fill_form(form)
        form.get_by_role('button',name='판정 저장',exact=True).click()
        expect(form.get_by_role('status')).to_contain_text('저장했습니다')
        path = tmp_path/'runs/review-run/summary.json'
        summary = json.loads(path.read_text())
        summary['evaluator']['feature_checks'][0]['reason'] = '새 근거 버전'
        path.write_text(json.dumps(summary))
        page.reload()
        page.locator('#tab-board').click()
        expect(page.locator('#cards .badge')).to_have_text('사람 검토 전')
        card = page.request.get(review_dashboard+'/api/run/review-run').json()['cards'][0]
        reports = download_reports(page,tmp_path)
        assert json.loads(reports['json'])['cards'][0]['latest_review'] is None
        for kind in ('md','html'):
            assert card['card_version'] in reports[kind]
            assert '판정: valid' not in reports[kind]
            assert '상태: 사람 검토 전' in reports[kind]
        browser.close()


@pytest.mark.parametrize('verification,termination,checks', [
    ('success','scenario_completed',[{'id':'ok','label':'정상 점검','status':'pass'}]),
    ('unknown','interrupted',[]),
    ('failure','scenario_failed',[{'id':'missing','label':'근거 누락 후보','status':'fail','step_id':6}]),
    ('unknown','scenario_unverified',[]),
])
def test_demo_states_keep_verification_termination_and_missing_evidence(review_dashboard,tmp_path,verification,termination,checks):
    path=tmp_path/'runs/review-run/summary.json'
    path.write_text(json.dumps({'verification':verification,'termination_reason':termination,
                               'evaluator':{'feature_checks':checks}}),encoding='utf-8')
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(accept_downloads=True,viewport={'width':390,'height':844})
        page.goto(review_dashboard)
        page.locator('#tab-history').click()
        expect(page.locator('#run-status')).to_contain_text({'success':'성공 확인','failure':'실패 확인','unknown':'미확인'}[verification])
        expect(page.locator('#shot-wrap')).to_contain_text('저장된 관찰 화면이 없습니다')
        page.locator('#tab-board').click()
        if checks and verification=='failure':
            expect(page.locator('#cards')).to_contain_text('근거 누락 후보')
            expect(page.locator('#cards [data-evidence-step]')).to_have_count(0)
        else:
            expect(page.locator('#cards')).to_contain_text('개선 후보가 없습니다')
        reports=download_reports(page,tmp_path)
        exported=json.loads(reports['json'])
        assert exported['summary']['verification']==verification
        assert exported['summary']['termination_reason']==termination
        for kind in ('md','html'):
            assert termination in reports[kind]
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()
