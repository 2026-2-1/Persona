import pytest
from playwright.sync_api import sync_playwright, expect
from test_review_form_browser import review_dashboard


@pytest.mark.parametrize('recovery,label', [
    ({}, '미확인'),
    ({'episodes': [], 'rate': None}, '대상 사건 없음'),
    ({'episodes': [{}], 'rate': None}, '미확인'),
    ({'episodes': [{}], 'rate': 0}, '0.0%'),
])
def test_recovery_rate_keeps_missing_zero_and_no_events_distinct(review_dashboard, recovery, label):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        payload = page.request.get(review_dashboard+'/api/run/review-run').json()
        payload['metrics']['recovery'] = recovery
        page.route('**/api/run/review-run', lambda r: r.fulfill(json=payload))
        page.goto(review_dashboard)
        page.locator('#tab-history').click()
        expect(page.locator('#run-metrics .metric-grid > div').filter(has_text='오류 후 재개율').locator('strong')).to_have_text(label)
        browser.close()
