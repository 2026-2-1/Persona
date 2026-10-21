import json

import pytest

from uxagent.actions import ActionExecutor
from uxagent.browser import BrowserSession
from uxagent.interaction import InteractionFlow
from uxagent.observation import observe
from uxagent.schemas import Action, ElementInfo, Observation, PopupChoice, UAction, SearchChoice


class FlowFast:
    def __init__(self, root=None, *, query='러닝화', choice='interact'):
        self.artifact_root = root
        self.query = query
        self.choice = choice
        self.calls = []

    @staticmethod
    def _u_persona(persona, mode):
        return '{}'

    async def _generate(self, stage, prompt, payload, *, response_model=None, image_path=None):
        self.calls.append((stage, payload, image_path))
        if stage == 'search_query':
            return SearchChoice(use_search=True, query=self.query, reason='페르소나에게 맞는 검색어')
        if stage == 'popup_decision':
            if self.choice == 'ignore':
                return PopupChoice(choice='ignore', reason='방해하지 않는 비모달')
            return PopupChoice(choice='interact', reason='닫기', action=UAction(
                action='click', target='close', description='팝업 닫기'))
        raise AssertionError(stage)


def search_observation(*, value='', focused=True, url='https://shop.test'):
    element = ElementInfo(id='search', role='textbox', name='상품 검색', value=value, focused=focused)
    return Observation(observation_id='obs', tab_id='tab-1', url=url, title='shop', html='<input>',
        input_elements=[element], interaction_state={'inputs':[{'id':'search','name':'상품 검색','value':value,
            'focused':focused,'enabled':True,'search':True}], 'scroll_regions':[]})


@pytest.mark.asyncio
async def test_search_click_continues_to_query_fill_then_submit_without_refocusing():
    flow, fast = InteractionFlow(), FlowFast()
    obs = search_observation()
    flow.remember(UAction(action='click', target='search', description='검색창 열기'), obs)
    assert flow.search['phase'] == 'opened'

    plan, fill, _ = await flow.propose(fast, object(), '러닝화', obs, 'persona', {'ok':True})
    assert fast.calls[0][0] == 'search_query'
    assert fill.actions[0].action == 'type'
    assert fill.actions[0].text == '러닝화'
    assert fill.actions[0].enter is False
    assert fill.actions[0].target == 'search'
    flow.remember(fill.actions[0], obs)

    filled = search_observation(value='러닝화')
    plan, submit, _ = await flow.propose(fast, object(), '러닝화', filled, 'persona', {'ok':True})
    assert submit.actions[0].action == 'key_press'
    assert submit.actions[0].key == 'Enter'
    assert submit.actions[0].target == 'search'
    assert flow.search['phase'] == 'submitted'


@pytest.mark.asyncio
async def test_decathlon_search_uses_visible_all_results_instead_of_enter():
    flow, fast = InteractionFlow(), FlowFast(query='러닝화')
    opened = search_observation()
    flow.remember(UAction(action='click', target='search', description='검색창 열기'), opened)
    await flow.propose(fast, object(), '러닝화', opened, 'persona', {'ok':True})
    filled = search_observation(value='러닝화', url='https://www.decathlon.co.kr/')
    from uxagent.schemas import ElementInfo
    filled.clickable_elements = [ElementInfo(id='all-results', role='link', name='러닝화 다음에 대한 모든 결과 보기')]
    _, submit, _ = await flow.propose(fast, object(), '러닝화', filled, 'persona', {'ok':True})
    assert submit.actions[0].action == 'click'
    assert submit.actions[0].target == 'all-results'


@pytest.mark.asyncio
async def test_search_query_can_be_declined_without_a_forced_search():
    class DeclineFast(FlowFast):
        async def _generate(self, stage, *args, **kwargs):
            self.calls.append((stage, args[1], None))
            return SearchChoice(use_search=False, query=None, reason='메뉴 탐색을 선호함')
    flow, fast = InteractionFlow(), DeclineFast()
    obs = search_observation()
    flow.remember(UAction(action='click', target='search', description='검색창 열기'), obs)
    assert await flow.propose(fast, object(), '러닝화', obs, 'persona', {'ok':True}) is None
    assert flow.search is None
    assert flow.context['search_transition'] == '메뉴 탐색을 선호함'


@pytest.mark.asyncio
async def test_popup_request_contains_popup_only_and_cropped_image_fallback(tmp_path):
    popup = {'id':'popup','name':'promotion','text':'','text_available':False,'modal':True,
        'controls':[{'id':'close','name':'닫기'}], 'scroll_ids':[],
        'clip':{'x':20,'y':30,'width':100,'height':80}}
    obs = Observation(observation_id='obs', tab_id='tab-1', url='https://shop.test', title='shop',
        html='<main>BACKGROUND_PRIVATE_TEXT</main>',
        clickable_elements=[ElementInfo(id='close',role='button',name='닫기'),
            ElementInfo(id='background',role='link',name='배경 이동')],
        interaction_state={'popup':popup,'scroll_regions':[]})
    image=(tmp_path/'popup.png'); image.write_bytes(b'crop')
    popup['screenshot_path']='popup.png'
    flow, fast=InteractionFlow(),FlowFast(tmp_path)
    result=await flow.propose(fast, object(), '과업', obs, 'persona', None)
    stage,payload,image_path=fast.calls[0]
    assert stage=='popup_decision'
    assert image_path==image
    assert 'BACKGROUND_PRIVATE_TEXT' not in json.dumps(payload,ensure_ascii=False)
    assert payload['popup'].get('popup_text') is None
    assert result[1].actions[0].target=='close'


@pytest.mark.asyncio
async def test_popup_ignore_is_not_allowed_for_modal():
    class IgnoreFast(FlowFast):
        async def _generate(self, stage, *args, **kwargs):
            return PopupChoice(choice='ignore',reason='skip')
    popup={'id':'p','name':'modal','text':'offer','text_available':True,'modal':True,'controls':[],
           'scroll_ids':[],'clip':{'x':0,'y':0,'width':100,'height':100}}
    obs=Observation(observation_id='obs',tab_id='tab-1',url='https://shop.test',title='shop',html='<body/>',
        interaction_state={'popup':popup,'scroll_regions':[]})
    with pytest.raises(ValueError,match='popup_decision_invalid'):
        await InteractionFlow().propose(IgnoreFast(),object(),'task',obs,'persona',None)


@pytest.mark.asyncio
async def test_scroll_moves_page_and_inner_regions_by_pixels_and_reports_progress():
    markup='''<div id=panel style="width:180px;height:160px;overflow:auto;white-space:nowrap">
      <div style="width:900px;height:900px">''' + ''.join(f'<p>{i}</p>' for i in range(60)) + '''</div></div>
      <div style="height:1800px">끝</div>'''
    async with BrowserSession(False, 800, 500) as browser:
        await browser.context.route('https://shop.test/**',
            lambda route: route.fulfill(body=markup, content_type='text/html'))
        await browser.active.goto('https://shop.test/')
        obs,_=await observe(browser)
        panel=next(r for r in obs.interaction_state['scroll_regions'] if r['id'] != 'page')
        result=await ActionExecutor(browser,[],1000,0).execute(Action(type='scroll',observation_id=obs.observation_id,
            tab_id=obs.tab_id,target_id=panel['id'],scroll_direction='right',scroll_amount=1000))
        assert result.ok
        assert result.interaction['moved'] is True
        assert result.interaction['direction']=='right'
        obs,_=await observe(browser)
        result=await ActionExecutor(browser,[],1000,0).execute(Action(type='scroll',observation_id=obs.observation_id,
            tab_id=obs.tab_id,scroll_direction='down',scroll_amount=1000))
        assert result.ok
        assert result.interaction['moved'] is True
        assert result.interaction['direction']=='down'
        assert result.interaction['after']-result.interaction['before'] <= 400
