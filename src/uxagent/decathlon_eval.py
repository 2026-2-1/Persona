"""DOM-only sports retail checks; no model claims or fixture JavaScript state."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit


DEFAULT_PROFILE = {
    'synthetic': True,
    'selectors': {
        'query': '[aria-label="상품 검색"]', 'applied_query': '#applied-query',
        'results': '#results', 'cards': '[data-product]',
        'card_name': '.product-name', 'card_price': '.product-price', 'card_color': '.product-color',
        'empty': '#empty-results', 'color': '[aria-label="검정"]',
        'max_price': '[aria-label="최대 가격"]', 'applied_color': '#applied-color',
        'applied_price': '#applied-price', 'detail': '[data-detail]',
        'detail_fields': {k: f'[data-field="{k}"]' for k in ('name', 'price', 'color', 'sizes', 'use', 'stock', 'pickup')},
    },
}


def parse_price(value):
    """Accept one non-negative amount with optional KRW marker; missing is unknown."""
    text = '' if value is None else str(value).strip()
    text = re.sub(r'^(?:₩|KRW)\s*', '', text, flags=re.I)
    text = re.sub(r'\s*(?:원|KRW)$', '', text, flags=re.I)
    if not re.fullmatch(r'(?:\d{1,3}(?:[,\s]\d{3})+|\d+)(?:\.\d{1,2})?', text):
        return None
    return float(re.sub(r'[,\s]', '', text))


async def evaluate_decathlon(page, task_id, expectations=None, profile=None):
    expectations = dict(expectations or {})
    if profile is None:
        if not await page.locator('[data-persona-fixture="decathlon-synthetic-v1"]').count():
            return {'verification': 'unknown', 'reason': 'selector_profile_required', 'feature_checks': []}
        profile = DEFAULT_PROFILE
    if profile.get('kind') == 'decathlon_public_live':
        return await _evaluate_public_live(page, task_id, expectations, profile)
    selectors = profile.get('selectors', {})
    labels = {'search': '검색 결과 일치', 'empty_search': '빈 검색 결과 안내', 'filters': '조건 필터 적용',
              'reset_filters': '필터 초기화와 결과 복원', 'detail': '상품 상세 필수 정보'}
    if task_id not in labels:
        return {'verification': 'unknown', 'reason': 'unknown_task', 'feature_checks': []}
    evidence = {'task_id': task_id, 'source': 'rendered_dom', 'synthetic': bool(profile.get('synthetic'))}

    def outcome(status, reason):
        return {'verification': {'pass': 'success', 'fail': 'failure', 'unknown': 'unknown'}[status],
                'reason': reason, 'feature_checks': [{'id': task_id, 'label': labels[task_id],
                                                     'status': status, 'evidence': dict(evidence)}]}

    async def node(key):
        selector = selectors.get(key)
        if not isinstance(selector, str) or not selector:
            return None
        locator = page.locator(selector)
        if await locator.count() != 1 or not await locator.is_visible():
            return None
        return locator

    async def text(key):
        locator = await node(key)
        return (await locator.inner_text()).strip() if locator else None

    try:
        if task_id == 'detail':
            detail = await node('detail')
            if detail is None:
                return outcome('unknown', 'detail_evidence_unavailable')
            fields = selectors.get('detail_fields', {})
            required = expectations.get('required_fields', ['name', 'price', 'color', 'sizes', 'use', 'stock', 'pickup'])
            if not required or any(not isinstance(fields.get(k), str) or not fields[k] for k in required):
                return outcome('unknown', 'detail_selectors_unavailable')
            values = {}
            for key in required:
                locator = detail.locator(fields[key])
                values[key] = ((await locator.inner_text()).strip()
                               if await locator.count() == 1 and await locator.is_visible() else '')
            evidence['fields'] = values
            evidence['expected'] = expectations
            if any(not value for value in values.values()):
                return outcome('fail', 'required_detail_information_missing')
            if 'price' in values and parse_price(values['price']) is None:
                return outcome('fail', 'detail_price_invalid')
            name = expectations.get('product_name')
            if name and values.get('name') != name:
                return outcome('fail', 'detail_product_mismatch')
            if expectations.get('color') and values.get('color') != expectations['color']:
                return outcome('fail', 'detail_color_mismatch')
            if expectations.get('max_price') is not None:
                price = parse_price(values.get('price'))
                limit = parse_price(expectations['max_price'])
                if price is None or limit is None:
                    return outcome('unknown', 'detail_price_evidence_unavailable')
                if price > limit:
                    return outcome('fail', 'detail_price_mismatch')
            return outcome('pass', 'detail_information_verified')

        query_input = await node('query')
        applied_query = await text('applied_query')
        results = await node('results')
        # Empty grid containers can have zero height; the visible empty-state
        # message supplies the presentation evidence in that case.
        if results is None and task_id == 'empty_search' and await text('empty'):
            selector = selectors.get('results')
            if selector and await page.locator(selector).count() == 1:
                results = page.locator(selector)
        if query_input is None or applied_query is None or results is None or not selectors.get('cards'):
            return outcome('unknown', 'search_evidence_unavailable')
        query = expectations.get('query', await query_input.input_value()).strip()
        evidence.update(query=query, query_input=await query_input.input_value(), applied_query=applied_query)
        cards = []
        for card in await results.locator(selectors['cards']).all():
            if not await card.is_visible():
                continue
            values = {}
            for field in ('name', 'price', 'color'):
                selector = selectors.get('card_' + field)
                if not selector:
                    return outcome('unknown', 'card_selectors_unavailable')
                field_node = card.locator(selector)
                values[field] = ((await field_node.inner_text()).strip()
                                 if await field_node.count() == 1 and await field_node.is_visible() else None)
            cards.append(values)
        evidence['results'] = cards
        if not query:
            return outcome('unknown', 'expected_query_required')
        if applied_query.casefold() != query.casefold() or evidence['query_input'].strip().casefold() != query.casefold():
            return outcome('fail', 'query_not_applied')
        if task_id == 'empty_search':
            empty_text = await text('empty')
            evidence['empty_message'] = empty_text
            if cards:
                return outcome('fail', 'unexpected_search_results')
            return outcome('pass', 'empty_results_verified') if empty_text else outcome('unknown', 'empty_message_unavailable')
        if not cards:
            return outcome('fail', 'expected_results_missing')
        if any(c['name'] is not None and query.casefold() not in c['name'].casefold() for c in cards):
            return outcome('fail', 'search_results_mismatch')
        if any(c['name'] is None for c in cards):
            return outcome('unknown', 'product_names_unavailable')
        if task_id == 'search':
            return outcome('pass', 'search_results_verified')
        color_node, price_node = await node('color'), await node('max_price')
        applied_color, applied_price = await text('applied_color'), await text('applied_price')
        if color_node is None or price_node is None or applied_color is None or applied_price is None:
            return outcome('unknown', 'filter_evidence_unavailable')
        selected_color = await color_node.is_checked()
        selected_price = await price_node.input_value()
        evidence.update(selected_color=selected_color, selected_price=selected_price,
                        applied_color=applied_color, applied_price=applied_price)
        if task_id == 'reset_filters':
            if selected_color or selected_price or applied_color != '전체' or applied_price != '제한 없음':
                return outcome('fail', 'filters_not_reset')
            minimum = expectations.get('minimum_results')
            if minimum is None:
                return outcome('unknown', 'reset_result_expectation_required')
            if len(cards) < minimum:
                return outcome('fail', 'results_not_restored')
            return outcome('pass', 'filter_reset_verified')
        color, limit = expectations.get('color'), parse_price(expectations.get('max_price'))
        if not color or limit is None:
            return outcome('unknown', 'filter_expectations_required')
        evidence['expected'] = {'color': color, 'max_price': limit}
        if not selected_color or applied_color != color or parse_price(selected_price) != limit or parse_price(applied_price) != limit:
            return outcome('fail', 'filters_not_applied')
        if any((c['color'] is not None and c['color'] != color)
               or (parse_price(c['price']) is not None and parse_price(c['price']) > limit) for c in cards):
            return outcome('fail', 'filtered_results_mismatch')
        if any(c['color'] is None or parse_price(c['price']) is None for c in cards):
            return outcome('unknown', 'product_filter_values_unavailable')
        return outcome('pass', 'filtered_results_verified')
    except Exception:
        return outcome('unknown', 'dom_evaluation_error')


async def _evaluate_public_live(page, task_id, expectations, profile):
    """Optional partial checks using explicitly supplied, externally audited selectors."""
    labels = {'search': '공개 검색 입력과 표시 이름', 'search_results': '공개 검색 URL과 표시 이름', 'filters_price': '공개 검색의 최대 가격',
              'detail_basic': '공개 상품 상세의 이름·가격'}
    if task_id not in labels:
        return {'verification': 'unknown', 'reason': 'unsupported_public_live_task', 'feature_checks': []}
    selectors = profile.get('selectors', {})
    evidence = {'task_id': task_id, 'source': 'rendered_dom_and_url', 'synthetic': False,
                'partial': True, 'profile_kind': 'decathlon_public_live',
                'scope': 'detail_name_price' if task_id == 'detail_basic' else 'visible_cards'}

    def outcome(status, reason):
        return {'verification': {'pass': 'success', 'fail': 'failure', 'unknown': 'unknown'}[status],
                'reason': reason, 'feature_checks': [{'id': task_id, 'label': labels[task_id],
                                                     'status': status, 'evidence': dict(evidence)}]}

    async def visible_nodes(scope, key):
        selector = selectors.get(key)
        if not isinstance(selector, str) or not selector:
            return []
        return [node for node in await scope.locator(selector).all() if await node.is_visible()]

    async def consistent_text(scope, key, *, price=False):
        nodes = await visible_nodes(scope, key)
        if not nodes:
            return None
        values = [' '.join((await node.inner_text(timeout=1000)).split()) for node in nodes]
        # Do not discard blank or conflicting duplicate nodes: neither is a
        # reliable assertion about the currently displayed product.
        normalized = [parse_price(value) for value in values] if price else values
        if any(value is None or value == '' for value in normalized) or len(set(normalized)) != 1:
            return None
        return normalized[0]

    try:
        if task_id == 'detail_basic':
            evidence['checked_fields'] = ['name', 'price']
            evidence['unchecked_fields'] = ['color', 'stock', 'pickup', 'sizes', 'use']
            name = await consistent_text(page, 'detail_name')
            price = await consistent_text(page, 'detail_price', price=True)
            evidence.update(name=name, price=price)
            expected_name = ' '.join(str(expectations.get('product_name') or '').split())
            limit = parse_price(expectations.get('max_price'))
            evidence['expected'] = {'product_name': expected_name, 'max_price': limit}
            if not expected_name or limit is None:
                return outcome('unknown', 'basic_detail_expectations_required')
            if name is not None and name != expected_name:
                return outcome('fail', 'detail_product_mismatch')
            if price is not None and price > limit:
                return outcome('fail', 'detail_price_mismatch')
            if name is None or price is None:
                return outcome('unknown', 'basic_detail_evidence_unavailable_or_ambiguous')
            return outcome('pass', 'partial_detail_name_price_verified')

        query = str(expectations.get('query') or '').strip()
        if not query:
            return outcome('unknown', 'expected_query_required')
        params = parse_qs(urlsplit(page.url).query, keep_blank_values=True)
        url_queries = params.get('query', [])
        url_query = url_queries[0].strip() if len(url_queries) == 1 else None
        evidence.update(query=query, url_query=url_query)
        query_values = [url_query]
        if task_id == 'search':
            inputs = await visible_nodes(page, 'query')
            input_query = (await inputs[0].input_value(timeout=1000)).strip() if len(inputs) == 1 else None
            evidence['query_input'] = input_query
            query_values.append(input_query)
        else:
            evidence['unchecked_fields'] = ['query_input', 'form_submission']
        if any(value is not None and value.casefold() != query.casefold() for value in query_values):
            return outcome('fail', 'query_not_applied')
        if any(value is None for value in query_values):
            return outcome('unknown', 'public_query_evidence_unavailable')
        results = await visible_nodes(page, 'results')
        if len(results) != 1:
            return outcome('unknown', 'public_results_selector_unavailable')
        card_nodes = await visible_nodes(results[0], 'cards')
        if not card_nodes:
            return outcome('unknown', 'public_product_data_unavailable')
        cards = []
        for card in card_nodes:
            cards.append({'name': await consistent_text(card, 'card_name'),
                          'price': await consistent_text(card, 'card_price', price=True) if task_id == 'filters_price' else None})
        evidence['results'] = cards
        if any(card['name'] is not None and query.casefold() not in card['name'].casefold() for card in cards):
            return outcome('fail', 'search_results_mismatch')
        if task_id in ('search', 'search_results'):
            if any(card['name'] is None for card in cards):
                return outcome('unknown', 'public_product_names_unavailable_or_ambiguous')
            return outcome('pass', 'partial_search_results_verified' if task_id == 'search_results' else 'partial_search_names_verified')

        limit = parse_price(expectations.get('max_price'))
        prices = params.get('price', [])
        bounds = re.fullmatch(r'\s*(\d+)\s+TO\s+(\d+)\s*', prices[0], flags=re.I) if len(prices) == 1 else None
        upper = parse_price(bounds.group(2)) if bounds else None
        evidence.update(expected_max_price=limit, url_price_upper=upper)
        if limit is None:
            return outcome('unknown', 'price_filter_expectation_required')
        if upper is not None and upper != limit:
            return outcome('fail', 'price_filter_not_applied')
        if any(card['price'] is not None and card['price'] > limit for card in cards):
            return outcome('fail', 'filtered_results_mismatch')
        if bounds is None or int(bounds.group(1)) > int(bounds.group(2)):
            return outcome('unknown', 'public_price_filter_evidence_unavailable')
        if any(card['name'] is None or card['price'] is None for card in cards):
            return outcome('unknown', 'public_product_values_unavailable_or_ambiguous')
        return outcome('pass', 'partial_price_filter_verified')
    except Exception:
        return outcome('unknown', 'dom_evaluation_error')
