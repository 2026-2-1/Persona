import json

import pytest

from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager, LocalQwenProvider
from uxagent.schemas import ElementInfo, UPlan
from test_u_fast import setup


@pytest.mark.asyncio
async def test_many_targets_are_chosen_hierarchically_before_executing_one_original_id():
    _, obs, *_ = setup()
    provider, logs, seen = LocalQwenProvider(), [], []
    targets = [ElementInfo(id=f'original.long.path.button-{i}', role='button',
        name=f'러닝 상품 {i} ' + '상세 이름과 표시된 가격 정보 ' * 3) for i in range(500)]
    obs.html = '<main>' + ''.join(f'<button parser-semantic-id="{e.id}">{e.name}</button>' for e in targets) + '</main>'
    obs.clickable_elements, obs.input_elements, obs.hoverable_elements, obs.select_elements = targets, [], [], []
    def complete(messages, model, temperature, max_tokens):
        assert provider.prompt_guard.fits(messages, max_tokens)
        stage = messages[0]['content'].split('FAST_STAGE:', 1)[1].splitlines()[0]
        payload = json.loads(messages[1]['content'])
        seen.append((stage, payload))
        if stage == 'target_selection':
            result = {'group_id': payload['groups'][0]['group_id'], 'reason': '현재 구역의 상품 확인'}
        elif stage == 'prompt_summary':
            result = {'summary': '러닝 상품의 이름과 가격 정보가 있는 화면이다.'}
        else:
            result = {'actions': [{'action': 'click', 'target': payload['valid_targets']['clickable'][0],
                                    'description': '선택한 구역의 상품 확인'}]}
        return json.dumps(result, ensure_ascii=False), {'provider': 'gpu', 'model': model,
            'input_tokens': 5, 'output_tokens': 5}
    provider._complete = complete
    fast = FastLoop(provider, BudgetManager(None, None), 'persona-qwen', .2, 512, logs.append)
    brain, *_ = setup()
    result = await fast.act(brain.persona, '러닝 상품 상세 확인', obs, [],
                           UPlan(plan='상품 찾기', rationale='과업 확인', next_step='상품 상세 열기'))
    choices = [payload for stage, payload in seen if stage == 'target_selection']
    assert len(choices) >= 2
    assert sum(group['count'] for group in choices[0]['groups']) == 500
    final = next(payload for stage, payload in seen if stage == 'decision')
    assert len(final['valid_targets']['clickable']) <= 24
    assert targets[0].name in final['environment']
    assert result.actions[0].target == targets[0].id
    assert fast.budget.requests == len(logs) == len(seen)


def test_compact_action_and_plan_instructions_keep_the_response_contracts():
    assert len(FastLoop._u_prompt('action')) < 2400
    assert len(FastLoop._u_prompt('planning')) < 1800
    assert '"actions"' in FastLoop._u_prompt('action')
    assert '"next_step"' in FastLoop._u_prompt('planning')


def test_control_regions_distinguish_dialog_navigation_and_product_section():
    result = FastLoop._control_regions('''<header><a parser-semantic-id="running">러닝</a></header>
    <section><h2><span>러닝화 상품</span></h2><button parser-semantic-id="shoe">킵코어</button></section>
    <div role="dialog" aria-label="프로모션"><button parser-semantic-id="close">닫기</button></div>''')
    assert result == {'running': '상단', 'shoe': '러닝화 상품', 'close': '프로모션'}
