from pathlib import Path

import pytest
from playwright.async_api import async_playwright
from pydantic import ValidationError

from uxagent.evaluator import evaluate
from uxagent.schemas import StudyConfig


def test_evaluation_check_contract():
    base = dict(study_id='test', start_url='https://shop.test', task='search', allowed_origins=['https://shop.test'])
    check = dict(id='result', label='검색 결과', kind='text_contains', selector='#result', expected='가방')
    config = StudyConfig(**base, evaluation_checks=[check])
    assert config.evaluation_checks[0].expected == '가방'
    for invalid in [dict(check, selector=None), dict(check, expected=''), dict(check, unexpected=True)]:
        with pytest.raises(ValidationError):
            StudyConfig(**base, evaluation_checks=[invalid])
    with pytest.raises(ValidationError):
        StudyConfig(**base, evaluation_checks=[check, check])


@pytest.mark.asyncio
async def test_external_checks_require_actual_visible_dom():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content('<p id="result">검정 가방</p><p id="hidden" hidden>성공</p>')
        checks = [dict(id='result', label='검색 결과', kind='text_contains', selector='#result', expected='가방')]
        assert (await evaluate(page, 'external'))['verification'] == 'unknown'
        result = await evaluate(page, 'external', checks)
        assert result['verification'] == 'success'
        assert result['feature_checks'][0]['status'] == 'pass'
        for selector in ['#missing', '#hidden']:
            result = await evaluate(page, 'external', [dict(checks[0], selector=selector)])
            assert result['verification'] == 'failure'
        result = await evaluate(page, 'external', [dict(id='url', label='URL', kind='url_contains', expected='/completed')])
        assert result['verification'] == 'failure'
        result = await evaluate(page, 'external', [dict(id='url', label='URL', kind='url_contains', expected='about:blank')])
        assert result['verification'] == 'success'
        result = await evaluate(page, 'external', [dict(checks[0], selector='[')])
        assert result['verification'] == 'unknown'
        assert result['feature_checks'][0]['evidence'] == {'reason': 'check_error'}
        await browser.close()


@pytest.mark.asyncio
async def test_fixture_search_filters_detail_checks_detect_stale_results():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto((Path(__file__).parent / 'fixtures/shop.html').as_uri())
        initial = await evaluate(page, 'local-bag-detail-v1')
        assert initial['verification'] == 'failure'
        assert {c['id']: c['status'] for c in initial['feature_checks']} == {'search':'unknown', 'filters':'unknown', 'detail':'fail'}
        await page.locator('#query').fill('가방')
        stale = await evaluate(page, 'local-bag-detail-v1')
        assert stale['feature_checks'][0]['status'] == 'fail'
        await page.locator('#search').click()
        await page.locator('#color').select_option('검정')
        await page.locator('#price').select_option('30000')
        assert (await evaluate(page, 'local-bag-detail-v1'))['feature_checks'][1]['status'] == 'fail'
        await page.locator('#apply').click()
        await page.locator('[data-product="bag-black"]').click()
        result = await evaluate(page, 'local-bag-detail-v1')
        assert result['verification'] == 'success'
        assert all(c['status'] == 'pass' for c in result['feature_checks'])
        await page.locator('#detail-price').evaluate('(e) => e.textContent = ""')
        assert (await evaluate(page, 'local-bag-detail-v1'))['feature_checks'][2]['status'] == 'fail'
        await page.locator('#color').select_option('')
        await page.locator('#price').select_option('')
        await page.locator('#apply').click()
        assert (await evaluate(page, 'local-bag-detail-v1'))['feature_checks'][1]['status'] == 'unknown'
        await browser.close()
