"""Data retrieval failure must not become an empty, current result."""
from playwright.sync_api import sync_playwright, expect
from test_review_form_browser import review_dashboard, open_form, fill_form


def test_failed_detail_refresh_preserves_draft_but_blocks_save_and_export(review_dashboard):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        form = open_form(page, review_dashboard)
        fill_form(form)
        page.route('**/api/run/review-run', lambda r: r.fulfill(status=500, json={'error':'review_history_unavailable'}))
        expect(page.locator('#data-status')).to_contain_text('마지막 정상 조회')
        expect(form.get_by_label('검토 메모')).to_have_value('근거 확인 <b>테스트</b>')
        expect(form.get_by_role('button', name='판정 저장', exact=True)).to_be_disabled()
        page.locator('#tab-history').click()
        expect(page.locator('#exports a')).to_have_count(0)
        page.unroute('**/api/run/review-run')
        page.get_by_role('button', name='자료 다시 불러오기', exact=True).click()
        expect(page.locator('#data-status')).to_be_hidden()
        page.locator('#tab-board').click()
        expect(form.get_by_role('button', name='판정 저장', exact=True)).to_be_enabled()
        expect(form.get_by_label('검토 메모')).to_have_value('근거 확인 <b>테스트</b>')
        browser.close()


def test_first_detail_failure_is_not_an_empty_candidate_result(review_dashboard):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route('**/api/run/review-run', lambda r: r.fulfill(status=404, json={'error':'run_not_found'}))
        page.goto(review_dashboard)
        page.locator('#tab-board').click()
        expect(page.locator('#data-status')).to_contain_text('실행 상세를 불러오지 못했습니다')
        expect(page.locator('#cards')).not_to_contain_text('발견한 개선 후보가 없습니다')
        expect(page.locator('.review-form')).to_have_count(0)
        browser.close()


def test_comparison_failure_is_visible_without_blocking_review(review_dashboard):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route('**/api/experiments', lambda r: r.fulfill(status=500, json={'error':'failed'}))
        form = open_form(page, review_dashboard)
        expect(form.get_by_role('button', name='판정 저장', exact=True)).to_be_enabled()
        page.locator('#tab-compare').click()
        expect(page.locator('#data-status')).to_contain_text('비교 자료를 불러오지 못했습니다')
        expect(page.locator('#experiments')).not_to_contain_text('비교 기록이 없습니다')
        browser.close()


