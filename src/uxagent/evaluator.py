from __future__ import annotations

from urllib.parse import urlsplit
from .schemas import EvaluationCheck


def feature(check_id, label, status, evidence):
    return {'id': check_id, 'label': label, 'status': status, 'evidence': evidence}


async def configured_checks(page, checks):
    results = []
    for raw in checks:
        try:
            check = raw if isinstance(raw, EvaluationCheck) else EvaluationCheck.model_validate(raw)
            if check.kind == 'url_contains':
                matched = check.expected in page.url
                evidence = {'url': page.url, 'expected': check.expected}
            else:
                locator = page.locator(check.selector)
                count = await locator.count()
                visible = count == 1 and await locator.is_visible()
                text = await locator.inner_text(timeout=1000) if visible else ''
                matched = visible and (check.kind == 'visible' or check.expected in text)
                evidence = {'selector': check.selector, 'count': count, 'visible': visible, 'text': text[:2000], 'expected': check.expected}
            results.append(feature(check.id, check.label, 'pass' if matched else 'fail', evidence))
        except Exception:
            # Browser error messages may contain sensitive page content.
            check_id = raw.id if isinstance(raw, EvaluationCheck) else str(raw.get('id', 'invalid'))
            label = raw.label if isinstance(raw, EvaluationCheck) else str(raw.get('label', 'Invalid check'))
            results.append(feature(check_id, label, 'unknown', {'reason': 'check_error'}))
    return results


async def evaluate(page, evaluator_id: str, checks=None, *, expectations=None, profile=None) -> dict:
    extra = await configured_checks(page, checks or [])
    if evaluator_id.startswith('decathlon-') and evaluator_id.endswith('-v1'):
        from .decathlon_eval import evaluate_decathlon
        result = await evaluate_decathlon(page, evaluator_id[len('decathlon-'):-len('-v1')], expectations, profile)
        result['feature_checks'].extend(extra)
        if any(c['status'] == 'fail' for c in extra):
            result['verification'] = 'failure'
        elif any(c['status'] == 'unknown' for c in extra) and result['verification'] == 'success':
            result['verification'] = 'unknown'
        return result
    if evaluator_id != 'local-bag-detail-v1':
        statuses = {check['status'] for check in extra}
        verification = 'failure' if 'fail' in statuses else ('success' if statuses == {'pass'} else 'unknown')
        return {'verification': verification, 'reason': 'configured_checks' if extra else 'unknown_evaluator', 'feature_checks': extra}
    if not urlsplit(page.url).path.endswith('shop.html'):
        return {'verification': 'failure', 'reason': 'not_on_shop_page', 'feature_checks': extra}
    try:
        state = await page.evaluate("""() => {
            const visible=e=>!!e && e.getClientRects().length>0 && getComputedStyle(e).visibility!=='hidden';
            const q=document.querySelector('#query')?.value.trim().toLowerCase()||'';
            const color=document.querySelector('#color')?.value||'';
            const price=document.querySelector('#price')?.value||'';
            const cards=[...document.querySelectorAll('#products .product')].filter(visible).map(e=>({name:e.querySelector('h2')?.textContent||'',text:e.innerText,price:Number((e.querySelector('p')?.textContent||'').replace(/[^0-9]/g,''))}));
            const detail=document.querySelector('#detail'); const product=window.getActiveProduct?.();
            return {query:q,color,price,cards,visible:visible(detail),kind:product?.kind,colorActive:product?.color,priceActive:product?.price,
                detailName:document.querySelector('#detail-name')?.textContent||'',detailPrice:document.querySelector('#detail-price')?.textContent||'',detailColor:document.querySelector('#detail-color')?.textContent||''};
        }""")
        cards = state['cards']
        search_ok = bool(cards) and all(state['query'] in c['name'].lower() for c in cards)
        filters_set = state['color'] == '검정' and state['price'] == '30000'
        filters_ok = bool(cards) and all('색상: 검정' in c['text'] and 0 < c['price'] <= 30000 for c in cards)
        detail_ok = state['visible'] and bool(state['detailName']) and bool(state['detailPrice']) and bool(state['detailColor'])
        success = state['visible'] and state.get('kind') == '가방' and state.get('colorActive') == '검정' and isinstance(state.get('priceActive'), (int, float)) and state['priceActive'] <= 30000
        features = [
            feature('search', '검색 결과 일치', ('pass' if search_ok else 'fail') if state['query'] else 'unknown', {'query': state['query'], 'results': cards}),
            feature('filters', '검정 · 30,000원 이하 필터', ('pass' if filters_ok else 'fail') if filters_set else 'unknown', {'color':state['color'], 'max_price':state['price'], 'results':cards}),
            feature('detail', '상품 상세 정보 표시', 'pass' if detail_ok else 'fail', {'visible':state['visible'], 'name':state['detailName'], 'price':state['detailPrice'], 'color':state['detailColor']}),
        ]
        if extra:
            success = success and all(c['status'] == 'pass' for c in extra)
        verification = 'success' if success else 'failure'
        if extra and any(c['status'] == 'unknown' for c in extra) and all(c['status'] != 'fail' for c in extra):
            verification = 'unknown'
        return {'verification':verification, 'reason':'matching_detail_visible' if success else 'criteria_not_met', 'feature_checks':features + extra}
    except Exception:
        return {'verification':'unknown', 'reason':'evaluator_error', 'feature_checks':extra}
