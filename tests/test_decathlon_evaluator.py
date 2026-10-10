import json
from pathlib import Path

import pytest

from uxagent.browser import BrowserSession
from uxagent.decathlon_eval import DEFAULT_PROFILE, evaluate_decathlon, parse_price
from uxagent.evaluator import evaluate
from uxagent.runner import FixtureServer


@pytest.mark.asyncio
async def test_decathlon_dispatch_requires_rendered_search_evidence():
    async with BrowserSession(headed=False) as browser:
        await browser.active.set_content('''<main data-persona-fixture="decathlon-synthetic-v1">
          <input aria-label="상품 검색" value="가방"><span id="applied-query">가방</span>
          <div id="results"><article data-product="bad"><h2 class="product-name">신발</h2>
          <p class="product-price">20,000원</p><p class="product-color">검정</p></article></div>
          </main>''')
        result = await evaluate(browser.active, 'decathlon-search-v1')
        assert result['verification'] == 'failure'
        assert result['feature_checks'][0]['status'] == 'fail'


@pytest.mark.asyncio
async def test_decathlon_real_page_without_profile_is_unknown():
    async with BrowserSession(headed=False) as browser:
        await browser.active.set_content('<p>가방 상품 검색 성공</p>')
        result = await evaluate(browser.active, 'decathlon-search-v1')
        assert result['verification'] == 'unknown'


@pytest.fixture
def fixture_url():
    server = FixtureServer(0)
    assert server.start()
    try:
        yield f'http://127.0.0.1:{server.server.server_address[1]}/decathlon.html'
    finally:
        server.close()


async def search(page, query='가방'):
    await page.get_by_role('textbox', name='상품 검색').fill(query)
    await page.get_by_role('textbox', name='상품 검색').press('Enter')
    await page.locator('#loading').wait_for(state='hidden')


async def filters(page):
    await page.get_by_role('button', name='필터 열기').click()
    await page.get_by_role('checkbox', name='검정').check()
    await page.get_by_label('최대 가격').select_option('30000')
    await page.get_by_role('button', name='필터 적용').click()
    await page.locator('#loading').wait_for(state='hidden')


@pytest.mark.asyncio
async def test_real_browser_five_tasks_and_four_independent_defects(fixture_url):
    expected = {'query': '가방', 'color': '검정', 'max_price': 30000}
    async with BrowserSession(headed=False) as browser:
        page = browser.active
        await page.goto(fixture_url)
        await search(page)
        assert (await evaluate_decathlon(page, 'search', expected))['verification'] == 'success'
        await filters(page)
        good = await evaluate_decathlon(page, 'filters', expected)
        assert good['verification'] == 'success'
        assert len(good['feature_checks'][0]['evidence']['results']) == 1
        await page.get_by_role('button', name='러닝 가방 블랙 상세 보기').click()
        assert (await evaluate_decathlon(page, 'detail', dict(expected, product_name='러닝 가방 블랙')))['verification'] == 'success'
        await page.get_by_role('button', name='필터 초기화').click()
        await page.locator('#loading').wait_for(state='hidden')
        assert (await evaluate_decathlon(page, 'reset_filters', dict(expected, minimum_results=3)))['verification'] == 'success'
        await search(page, '찾을수없는합성상품')
        assert (await evaluate_decathlon(page, 'empty_search', {'query': '찾을수없는합성상품'}))['verification'] == 'success'
        for defect, task in [('search', 'search'), ('filter', 'filters'), ('reset', 'reset_filters'), ('detail', 'detail')]:
            await page.goto(f'{fixture_url}?defect={defect}')
            await search(page)
            if task in ('filters', 'reset_filters', 'detail'):
                await filters(page)
            if task == 'reset_filters':
                await page.get_by_role('button', name='필터 초기화').click()
                await page.locator('#loading').wait_for(state='hidden')
            if task == 'detail':
                await page.get_by_role('button', name='러닝 가방 블랙 상세 보기').click()
            result = await evaluate_decathlon(page, task, dict(expected, minimum_results=3, product_name='러닝 가방 블랙'))
            assert result['verification'] == 'failure', (defect, result)
            assert result['feature_checks'][0]['status'] == 'fail'


@pytest.mark.asyncio
async def test_rendered_dom_falsification_ignores_claims_and_attributes(fixture_url):
    expected = {'query': '가방', 'color': '검정', 'max_price': 30000}
    async with BrowserSession(headed=False) as browser:
        page = browser.active
        await page.goto(fixture_url)
        await search(page)
        await filters(page)
        # Correct data-price and arbitrary claims cannot hide the displayed expensive price.
        await page.locator('[data-product="bag-black"] .product-price').evaluate("e => e.textContent='₩ 99,000'")
        await page.evaluate("window.success=true;window.getActiveProduct=()=>({price:100,color:'검정'})")
        result = await evaluate_decathlon(page, 'filters', expected)
        assert result['verification'] == 'failure'
        assert result['reason'] == 'filtered_results_mismatch'
        await page.locator('.product-price').evaluate("e => e.textContent=''")
        assert (await evaluate_decathlon(page, 'filters', expected))['verification'] == 'unknown'
        await page.locator('.product-color').evaluate("e => e.textContent='파랑'")
        assert (await evaluate_decathlon(page, 'filters', expected))['verification'] == 'failure'
        await page.goto(fixture_url)
        await search(page)
        await page.get_by_role('textbox', name='상품 검색').fill('신발')
        assert (await evaluate_decathlon(page, 'search', {'query': '신발'}))['reason'] == 'query_not_applied'
        await search(page)
        await page.get_by_role('button', name='러닝 가방 블랙 상세 보기').click()
        await page.locator('[data-field="price"]').evaluate("e => e.textContent=''")
        assert (await evaluate_decathlon(page, 'detail'))['verification'] == 'failure'


@pytest.mark.asyncio
async def test_unknown_profile_and_optional_mapping(fixture_url):
    async with BrowserSession(headed=False) as browser:
        page = browser.active
        await page.goto(fixture_url)
        await search(page)
        await page.locator('main').evaluate("e => e.removeAttribute('data-persona-fixture')")
        assert (await evaluate_decathlon(page, 'search', {'query': '가방'}))['verification'] == 'unknown'
        mapping = json.loads(json.dumps(DEFAULT_PROFILE))
        mapping['synthetic'] = False
        result = await evaluate_decathlon(page, 'search', {'query': '가방'}, mapping)
        assert result['verification'] == 'success'
        assert result['feature_checks'][0]['evidence']['synthetic'] is False
        mapping['selectors']['card_name'] = '#unavailable'
        assert (await evaluate_decathlon(page, 'search', {'query': '가방'}, mapping))['verification'] == 'unknown'
        mapping['selectors']['query'] = '['
        assert (await evaluate_decathlon(page, 'search', {'query': '가방'}, mapping))['verification'] == 'unknown'


@pytest.mark.parametrize('raw,expected', [('30,000원', 30000), ('₩ 24,900', 24900), ('KRW 25 000', 25000),
                                        ('30000', 30000), ('12.50', 12.5), (0, 0), ('', None), (None, None),
                                        ('가격 미정', None), ('-100원', None), ('2~3만원', None)])
def test_price_never_coerces_unknown_to_zero(raw, expected):
    assert parse_price(raw) == expected


def test_exported_profile_matches_default_selectors():
    profile = json.loads((Path(__file__).parents[1] / 'configs/decathlon_profile.json').read_text(encoding='utf-8'))
    assert profile['selectors'] == DEFAULT_PROFILE['selectors']
    assert profile['synthetic'] is True


LIVE_PROFILE = {
    'kind': 'decathlon_public_live', 'synthetic': False,
    'selectors': {
        'query': '[data-cy="search-bar-desktop"] input', 'results': 'body',
        'cards': 'div[data-testid="producthit-tile-box"]', 'card_name': 'div[title]',
        'card_price': '[data-cy="item-current-price"]', 'detail_name': 'h1',
        'detail_price': '[data-cy="item-current-price"].vp-price-amount--large',
    },
}


def public_search_fragment(name='러닝 가방', price='79,900원'):
    return f'''<meta charset="utf-8"><div data-cy="search-bar-desktop"><input value="가방"></div>
        <div data-testid="producthit-tile-box"><div title="{name}">{name}</div>
        <span data-cy="item-current-price">{price}</span></div>'''


@pytest.mark.asyncio
async def test_public_live_profile_partial_search_and_price_filter_dom_only():
    async with BrowserSession(headed=False) as browser:
        page = browser.active
        await page.route('**/*', lambda route: route.fulfill(body=public_search_fragment(), content_type='text/html'))
        await page.goto('https://www.decathlon.co.kr/search?query=%EA%B0%80%EB%B0%A9&price=14900%20TO%2080000')
        expected = {'query': '가방', 'max_price': 80000}
        assert (await evaluate_decathlon(page, 'search', expected, LIVE_PROFILE))['verification'] == 'success'
        assert (await evaluate(page, 'decathlon-filters_price-v1', expectations=expected, profile=LIVE_PROFILE))['verification'] == 'success'
        filtered = await evaluate_decathlon(page, 'filters_price', expected, LIVE_PROFILE)
        assert filtered['verification'] == 'success'
        assert filtered['feature_checks'][0]['evidence']['scope'] == 'visible_cards'
        assert (await evaluate_decathlon(page, 'filters_price', expected))['verification'] == 'unknown'
        assert (await evaluate_decathlon(page, 'filters_price', expected, DEFAULT_PROFILE))['verification'] == 'unknown'
        await page.set_content(public_search_fragment(price='89,900원'))
        assert (await evaluate_decathlon(page, 'filters_price', expected, LIVE_PROFILE))['verification'] == 'failure'
        await page.set_content(public_search_fragment(name='신발', price=''))
        assert (await evaluate_decathlon(page, 'search', expected, LIVE_PROFILE))['verification'] == 'failure'
        await page.set_content(public_search_fragment(price=''))
        assert (await evaluate_decathlon(page, 'filters_price', expected, LIVE_PROFILE))['verification'] == 'unknown'
        await page.set_content(public_search_fragment() + '<div data-testid="producthit-tile-box" style="min-height:20px">불완전 상품</div>')
        assert (await evaluate_decathlon(page, 'search', expected, LIVE_PROFILE))['verification'] == 'unknown'
        await page.goto('https://www.decathlon.co.kr/search?query=%EA%B0%80%EB%B0%A9&price=14900%20TO%2090000')
        assert (await evaluate_decathlon(page, 'filters_price', expected, LIVE_PROFILE))['verification'] == 'failure'
        await page.goto('https://www.decathlon.co.kr/search?query=%EC%8B%A0%EB%B0%9C&price=14900%20TO%2080000')
        assert (await evaluate_decathlon(page, 'search', expected, LIVE_PROFILE))['verification'] == 'failure'


@pytest.mark.asyncio
async def test_public_live_basic_detail_duplicate_consistency_and_declared_scope():
    async with BrowserSession(headed=False) as browser:
        page = browser.active
        detail = '''<h1>러닝 가방</h1><span data-cy="item-current-price" class="vp-price-amount--large">79,900원</span>'''
        await page.set_content(detail + detail.replace('<h1>러닝 가방</h1>', ''))
        expected = {'product_name': '러닝 가방', 'max_price': 80000, 'color': '검정', 'required_fields': ['stock']}
        result = await evaluate_decathlon(page, 'detail_basic', expected, LIVE_PROFILE)
        assert result['verification'] == 'success'
        assert result['feature_checks'][0]['evidence']['checked_fields'] == ['name', 'price']
        assert result['feature_checks'][0]['evidence']['unchecked_fields'] == ['color', 'stock', 'pickup', 'sizes', 'use']
        await page.set_content(detail + detail.replace('<h1>러닝 가방</h1>', '').replace('79,900원', '69,900원'))
        assert (await evaluate_decathlon(page, 'detail_basic', expected, LIVE_PROFILE))['verification'] == 'unknown'
        await page.set_content(detail.replace('79,900원', '99,900원'))
        assert (await evaluate_decathlon(page, 'detail_basic', expected, LIVE_PROFILE))['verification'] == 'failure'
        await page.set_content(detail.replace('러닝 가방', '트레킹 신발'))
        assert (await evaluate_decathlon(page, 'detail_basic', expected, LIVE_PROFILE))['verification'] == 'failure'
        await page.set_content('<h1>러닝 가방</h1>')
        assert (await evaluate_decathlon(page, 'detail_basic', expected, LIVE_PROFILE))['verification'] == 'unknown'
        await page.set_content(detail)
        assert (await evaluate_decathlon(page, 'detail_basic', {}, LIVE_PROFILE))['verification'] == 'unknown'


@pytest.mark.asyncio
async def test_public_card_duplicate_names_do_not_use_title_as_hidden_truth():
    async with BrowserSession(headed=False) as browser:
        page = browser.active
        await page.route('**/*', lambda route: route.fulfill(body=public_search_fragment(), content_type='text/html'))
        await page.goto('https://www.decathlon.co.kr/search?query=%EA%B0%80%EB%B0%A9')
        await page.locator('[data-testid="producthit-tile-box"]').evaluate('''e => {
            const extra = document.createElement('div');extra.title='가방';extra.textContent='러닝 가방';e.append(extra);
        }''')
        assert (await evaluate_decathlon(page, 'search', {'query': '가방'}, LIVE_PROFILE))['verification'] == 'success'
        await page.locator('div[title]').last.evaluate("e=>e.textContent='트레킹 가방'")
        assert (await evaluate_decathlon(page, 'search', {'query': '가방'}, LIVE_PROFILE))['verification'] == 'unknown'


@pytest.mark.asyncio
async def test_public_result_url_scope_does_not_claim_form_submission():
    async with BrowserSession(headed=False) as browser:
        page = browser.active
        fragment = public_search_fragment().replace('value="가방"', 'value=""')
        await page.route('**/*', lambda route: route.fulfill(body=fragment, content_type='text/html'))
        await page.goto('https://www.decathlon.co.kr/search?query=%EA%B0%80%EB%B0%A9&price=14900%20TO%2080000')
        expected = {'query': '가방', 'max_price': 80000}
        assert (await evaluate_decathlon(page, 'search', expected, LIVE_PROFILE))['verification'] == 'failure'
        result = await evaluate_decathlon(page, 'search_results', expected, LIVE_PROFILE)
        assert result['verification'] == 'success'
        assert result['feature_checks'][0]['evidence']['unchecked_fields'] == ['query_input', 'form_submission']
        filtered = await evaluate_decathlon(page, 'filters_price', expected, LIVE_PROFILE)
        assert filtered['verification'] == 'success'
        assert filtered['feature_checks'][0]['evidence']['unchecked_fields'] == ['query_input', 'form_submission']
        await page.locator('[data-cy="search-bar-desktop"]').evaluate('e => e.remove()')
        assert (await evaluate_decathlon(page, 'search_results', expected, LIVE_PROFILE))['verification'] == 'success'
        assert (await evaluate_decathlon(page, 'search', expected, LIVE_PROFILE))['verification'] == 'unknown'
        assert (await evaluate_decathlon(page, 'filters_price', expected, LIVE_PROFILE))['verification'] == 'success'
        await page.locator('div[title]').evaluate("e=>e.textContent='트레킹 신발'")
        assert (await evaluate_decathlon(page, 'search_results', expected, LIVE_PROFILE))['verification'] == 'failure'
