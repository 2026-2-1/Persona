"""Regressions found while running Qwen on the synthetic and live Decathlon tasks."""
import json

import pytest

from uxagent.browser import BrowserSession
from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager
from uxagent.observation import observe
from uxagent.prompt_guard import PromptGuard
from uxagent.runner import load_study
from uxagent.schemas import Action, PopupChoice, UActions, UPlan
from test_extended_actions import setup_page


def test_hangul_is_estimated_per_character_not_per_byte():
    text = '가' * 1000
    estimate = PromptGuard.estimate([{'role': 'user', 'content': text}])
    assert 1000 <= estimate < 1100


@pytest.mark.parametrize('model, raw, repair', [
    (UPlan, {'plan': ['1. 필터 열기', '2. 상세 보기'], 'rationale': 'r', 'next_step': 'n'}, 'plan_list_joined'),
    (UActions, {'action': 'click', 'target': 'item1', 'description': 'd'}, 'single_action_wrapped'),
    (PopupChoice, {'choice': 'interact', 'reason': 'r',
                   'action': {'type': 'mouse_click', 'target': 'close', 'description': 'd'}}, 'action_type_key_renamed'),
])
def test_qwen_container_shapes_are_normalized_without_changing_values(model, raw, repair):
    repairs = []
    result = FastLoop._normalize_shape(raw, model, repairs)
    model.model_validate(result)
    assert repair in repairs


def test_targeted_mouse_click_without_coordinates_becomes_click():
    repairs = []
    result = FastLoop._normalize_shape({'choice': 'interact', 'reason': 'r', 'action': {
        'action': 'mouse_click', 'target': 'close', 'description': 'd'}}, PopupChoice, repairs)
    assert result['action']['action'] == 'click' and 'targeted_mouse_click_as_click' in repairs


@pytest.mark.asyncio
async def test_summary_slices_shrink_when_a_large_slice_does_not_fit():
    class Counter:
        def count(self, messages):
            return {'prompt_tokens': 9000 if any(len(m['content']) > 3000 for m in messages) else 200,
                    'tokenizer_fingerprint': 'same-model'}

    sizes = []

    async def summarize(messages, *args):
        sizes.append(len(json.loads(messages[-1]['content'])['content']))
        return '{"summary":"관찰 핵심"}', {'input_tokens': 1, 'output_tokens': 1}

    guard = PromptGuard(Counter())
    messages = [{'role': 'system', 'content': 'Keep all task facts.'},
                {'role': 'user', 'content': json.dumps({'memories': ['관찰 ' * 3000]}, ensure_ascii=False)}]
    prepared = await guard.prepare(messages, 'persona-qwen', 512, send=summarize, budget=BudgetManager(None, None))
    assert guard.fits(prepared, 512)
    assert sizes and max(sizes) <= 3000


@pytest.mark.asyncio
async def test_select_is_named_by_field_and_click_explains_select_action():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '''<label>최대 가격 <select id="max-price">
            <option value="">제한 없음</option><option value="30000">30,000원</option></select></label>''')
        obs, registry = await observe(browser)
        executor.publish(registry)
        select = obs.select_elements[0]
        assert select.id == 'max_price'
        result = await executor.execute(Action(type='click', observation_id=obs.observation_id,
                                               tab_id=obs.tab_id, target_id=select.id))
        assert result.error['code'] == 'not_interactable' and "'30000'" in result.error['message']


@pytest.mark.asyncio
async def test_ids_keep_one_parent_segment_and_product_links_use_their_number():
    banner = '15% 할인 쿠폰코드 WARM15 ' * 3
    async with BrowserSession(False) as browser:
        await setup_page(browser, f'''<div data-maybe-hoverable="true">{banner}
            <div data-maybe-hoverable="true">카드 <button>담기</button></div>
            <a href="/p/running-shoe-8913967.html">러닝화</a><a href="/p/running-shoe-8913967.html">러닝화 이미지</a></div>''')
        obs, _ = await observe(browser)
        ids = [element.id for element in obs.clickable_elements]
        assert all(len(element_id) <= 45 for element_id in ids)
        assert {'p_8913967', 'p_8913967_2'} <= set(ids)


def test_live_study_uses_a_persona_matching_its_task():
    _, persona, _ = load_study('configs/study-decathlon-live.json')
    assert '러닝화' in persona.intent and persona.constraints['budget_krw'] >= 80000
