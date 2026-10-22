import json

import pytest

from uxagent.browser import BrowserSession
from uxagent.observation import observe
from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager, LocalQwenProvider


@pytest.mark.asyncio
async def test_shared_context_distinguishes_cards_forms_options_and_explicit_relationships():
    markup = '''<main><h1>상점</h1>
      <section><h2>상품 목록</h2><article><h3>상품 A</h3><button>담기</button></article>
      <article><h3>상품 B</h3><button>담기</button></article></section>
      <form aria-label="배송 정보"><fieldset><legend>배송 날짜</legend>
        <label for=start>시작일</label><input id=start type=date required aria-describedby=help>
        <span id=help>도착일을 선택하세요</span><label for=end>종료일</label><input id=end type=date>
        </fieldset><button type=button>확인</button></form>
      <form aria-label="연락처"><label id=phone-title>전화번호</label>
        <input aria-labelledby=phone-title aria-invalid=true aria-errormessage=phone-error>
        <span id=phone-error role=alert>번호를 확인하세요</span><button type=button>확인</button></form>
      <div role=tablist aria-label="상품 정보"><button role=tab aria-selected=true aria-controls=panel>상세</button></div>
      <section id=panel role=tabpanel aria-label="상세 내용"><p>설명</p></section>
      <fieldset><legend>사이즈</legend><label><input type=radio name=size value=260 checked>260</label>
      <label><input type=radio name=size value=270 disabled>270 품절</label></fieldset>
      <select aria-label="색상"><option value=black>검정</option><option value=red disabled>빨강 품절</option></select>
      <input id=unknown><input type=password value="never-copy-this">
    </main>'''
    async with BrowserSession(False) as browser:
        await browser.active.set_content(markup)
        obs, registry = await observe(browser)
        groups = {g.id: g for g in obs.context_groups}
        buttons = [e for e in obs.clickable_elements if e.name == '담기']
        assert len(buttons) == 2
        owners = [{groups[g].name for g in e.context.group_ids} for e in buttons]
        assert '상품 A' in owners[0] and '상품 B' not in owners[0]
        assert '상품 B' in owners[1] and '상품 A' not in owners[1]
        phone = next(e for e in obs.input_elements if e.name == '전화번호')
        assert phone.context.name_source == 'aria-labelledby'
        assert phone.context.errors == ['번호를 확인하세요']
        assert phone.context.attributes['aria-invalid'] == 'true'
        start = next(e for e in obs.input_elements if e.name == '시작일')
        assert start.context.attributes['required'] == 'true'
        assert start.context.descriptions == ['도착일을 선택하세요']
        assert '배송 정보' in {groups[g].name for g in start.context.group_ids}
        unknown_id = await browser.active.locator('#unknown').get_attribute('parser-semantic-id')
        unknown = next(e for e in obs.input_elements if e.id == unknown_id)
        assert unknown.context.label_status == 'unknown'
        assert 'never-copy-this' not in obs.model_dump_json()
        unavailable = next(e for e in obs.context_only_elements if e.name == '270 품절')
        assert not unavailable.enabled and unavailable.id not in registry.targets
        color = next(e for e in obs.select_elements if e.name == '색상')
        assert color.context.option_states == [{'value':'red','label':'빨강 품절','disabled':'true'}]
        for e in obs.input_elements + obs.clickable_elements:
            assert all(g in groups for g in e.context.group_ids)
            assert e.id in registry.targets
        fast = FastLoop(LocalQwenProvider(), BudgetManager(None, None), 'persona-qwen', .2, 512)
        html, aliases, _ = fast._model_html(obs, force=True)
        assert '<element_context>' in html
        assert '상품 A' in html and '상품 B' in html
        assert aliases[buttons[0].id] in html


@pytest.mark.asyncio
async def test_repeated_div_cards_and_table_rows_keep_different_owners():
    markup = '''<main><div class=list><div class=card><h2>신발 A</h2><button>선택</button></div>
      <div class=card><h2>신발 B</h2><button>선택</button></div></div>
      <table><caption>주문</caption><thead><tr><th>상품</th><th>작업</th></tr></thead>
      <tbody><tr><th>주문 A</th><td><button>삭제</button></td></tr>
      <tr><th>주문 B</th><td><button>삭제</button></td></tr></tbody></table></main>'''
    async with BrowserSession(False) as browser:
        await browser.active.set_content(markup)
        obs, _ = await observe(browser)
        groups = {g.id: g for g in obs.context_groups}
        names = [{groups[g].name for g in e.context.group_ids} for e in obs.clickable_elements if e.name == '선택']
        assert any('신발 A' in x and '신발 B' not in x for x in names)
        assert any('신발 B' in x and '신발 A' not in x for x in names)
        deletes = [e for e in obs.clickable_elements if e.name == '삭제']
        assert all(e.context.attributes['column_header'] == '작업' for e in deletes)
        assert {groups[e.context.group_ids[-1]].name for e in deletes} == {'주문 A', '주문 B'}


@pytest.mark.asyncio
async def test_popup_scope_does_not_leak_background_context():
    from uxagent.dom_context import model_context
    markup = '''<main><h1>PRIVATE_BACKGROUND_NAME</h1><button>배경 확인</button>
      <div role=dialog aria-modal=true aria-label="알림"><h2>팝업 제목</h2><button>닫기</button></div></main>'''
    async with BrowserSession(False) as browser:
        await browser.active.set_content(markup)
        obs, _ = await observe(browser)
        close = next(e for e in obs.clickable_elements if e.name == '닫기')
        context = model_context(obs, target_ids=[close.id], popup_only=True)
        assert 'PRIVATE_BACKGROUND_NAME' not in json.dumps(context)
        assert context['groups'][0]['kind'] == 'dialog'
        assert not context['groups'][0].get('parent_id')


@pytest.mark.asyncio
async def test_prompt_reduction_preserves_shared_context_markup_exactly():
    provider = LocalQwenProvider()
    context = '<element_context>{"groups":[{"id":"context:g1","kind":"article","name":"신발 A"}],"elements":{"s1":{"group_ids":["context:g1"]}}}</element_context>'
    controls = '<controls><control id="s1">담기</control></controls>'
    messages = [{'role':'system','content':'Return JSON.'}, {'role':'user','content':json.dumps({
        'environment':'<visible_text>' + '관찰문 ' * 9000 + '</visible_text>' + controls + context},ensure_ascii=False)}]

    async def send(*args):
        return '{"summary":"관찰 핵심"}', {'input_tokens':1,'output_tokens':1}

    provider._enqueue = send
    prepared = await provider.prepare_messages(messages,'persona-qwen',512,budget=BudgetManager(None,None))
    environment = json.loads(prepared[1]['content'])['environment']
    assert context in environment and controls in environment
    assert environment.count('<element_context>') == 1


@pytest.mark.asyncio
async def test_hierarchical_target_selection_keeps_selected_owner_refs_and_aliases():
    from html import unescape
    import re
    from uxagent.schemas import ContextGroup, ElementContext, ElementInfo, Observation, UPlan, Persona
    from pathlib import Path

    targets = [ElementInfo(id=f'long.original.button.{i}',role='button',name='담기',context=ElementContext(
        name_source='text',label_status='explicit',group_ids=[f'context:g{i}'])) for i in range(120)]
    groups = [ContextGroup(id=f'context:g{i}',kind='article',name=f'상품 {i} '+ '설명'*65) for i in range(120)]
    obs = Observation(observation_id='obs',tab_id='tab-1',url='https://shop.test',title='shop',
        html='<main>'+'<button>상품 설명</button>'*500+'</main>',clickable_elements=targets,context_groups=groups)
    provider, captures = LocalQwenProvider(), []

    async def send(messages, model, temperature, max_tokens):
        stage = messages[0]['content'].split('FAST_STAGE:',1)[1].splitlines()[0]
        payload = json.loads(messages[-1]['content'])
        if stage == 'target_selection':
            value = {'group_id':payload['groups'][0]['group_id'],'reason':'상품 선택'}
        elif stage == 'prompt_summary':
            value = {'summary':'상품 목록'}
        else:
            captures.append(payload)
            value = {'actions':[{'action':'click','target':payload['valid_targets']['clickable'][0],'description':'상품 선택'}]}
        return json.dumps(value,ensure_ascii=False), {'provider':'gpu','model':model,'input_tokens':1,'output_tokens':1}

    provider._enqueue = send
    fast = FastLoop(provider,BudgetManager(None,None),'persona-qwen',0,512)
    persona = Persona.model_validate_json((Path(__file__).resolve().parents[1]/'configs/persona.json').read_text())
    chosen = await fast.act(persona,'상품 확인',obs,[],UPlan(plan='상품 확인',rationale='목표',next_step='상품 선택'))
    payload = captures[-1]
    context = json.loads(unescape(re.search(r'<element_context>(.*?)</element_context>',payload['environment'],re.S)[1]))
    assert len(context['groups']) < len(groups)
    assert set(context['elements']) <= set(payload['valid_targets']['clickable'])
    definitions = {g['id'] for g in context['groups']}
    assert all(set(item['group_ids']) <= definitions for item in context['elements'].values())
    assert chosen.actions[0].target in {e.id for e in targets}
