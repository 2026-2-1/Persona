import json

import pytest
from pydantic import ValidationError

from uxagent.actions import ActionExecutor
from uxagent.browser import BrowserSession
from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager
from uxagent.observation import observe
from uxagent.schemas import Action, ElementInfo, Observation, Persona, StudyConfig


def action_for(obs, kind, **fields):
    return Action(type=kind, observation_id=obs.observation_id, tab_id=obs.tab_id, **fields)


def target_id(obs, group, name):
    return next(element.id for element in getattr(obs, group) if element.name == name)


def test_legacy_scroll_and_u_key_action_schema():
    assert StudyConfig(study_id='s', start_url='https://shop.test', task='search',
                       allowed_origins=['https://shop.test'], explicit_scroll=True).explicit_scroll
    for key in ['Enter', 'Escape', 'Tab', 'ArrowUp', 'ArrowDown', 'Space']:
        assert Action(type='key_press', observation_id='o', tab_id='t', target_id='search', key=key).key == key
    assert Action(type='key_press', observation_id='o', tab_id='t', key='Control+Shift+P').key == 'Control+Shift+P'
    assert Action(type='scroll', observation_id='o', tab_id='t', scroll_direction='left', scroll_amount=1200).scroll_amount == 1200
    for distance in [-900, -1, 1, 900]:
        assert Action(type='scroll', observation_id='o', tab_id='t', scroll_y=distance).scroll_y == distance


@pytest.mark.parametrize('fields', [
    {'type':'key_press'},
    {'type':'key_press', 'target_id':'search', 'key':'Control+A', 'text':'script'},
    {'type':'key_press', 'target_id':'search', 'key':'Enter', 'text':'script'},
    {'type':'scroll', 'scroll_y':0}, {'type':'scroll', 'scroll_y':901},
    {'type':'scroll', 'scroll_y':-901}, {'type':'scroll', 'scroll_y':True},
    {'type':'scroll', 'scroll_y':2.5}, {'type':'scroll', 'scroll_y':100, 'target_id':'x'},
    {'type':'click', 'target_id':'x', 'key':'Enter'},
])
def test_action_rejects_unsafe_or_unrelated_fields(fields):
    with pytest.raises(ValidationError):
        Action(observation_id='o', tab_id='t', **fields)


@pytest.mark.parametrize('fields', [
    {'type':'click', 'target_id':'search', 'input_mode':'sequential'},
    {'type':'key_press', 'target_id':'search', 'key':'Enter', 'input_mode':'fill'},
    {'type':'scroll', 'scroll_y':100, 'input_mode':'sequential'},
    {'type':'type', 'target_id':'search', 'text':'shoes', 'input_mode':'script'},
])
def test_input_mode_is_an_explicit_type_only_option(fields):
    with pytest.raises(ValidationError):
        Action(observation_id='o', tab_id='t', **fields)


async def setup_page(browser, markup):
    await browser.context.route('https://shop.test/**', lambda route: route.fulfill(body=markup, content_type='text/html'))
    await browser.active.goto('https://shop.test/')
    return ActionExecutor(browser, ['https://shop.test'], timeout_ms=700, settle_ms=300, allow_scroll=True)


@pytest.mark.asyncio
async def test_sequential_input_updates_keyboard_driven_search_without_changing_fill_default():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '''<input aria-label="Search" value="old">
            <p id="result">No results</p><script>
            let query = '';
            const search = document.querySelector('input');
            search.onkeyup = event => {if(event.key !== 'Enter') query = search.value};
            search.onkeydown = event => {
              if(event.key === 'Enter') document.querySelector('#result').textContent = query ? 'Results for ' + query : 'No results';
            };
            </script>''')
        obs, registry = await observe(browser)
        executor.publish(registry)
        search = target_id(obs, 'input_elements', 'Search')
        default_input = action_for(obs, 'type', target_id=search, text='running shoes')
        assert (await executor.execute(default_input)).ok
        assert (await executor.execute(action_for(obs, 'key_press', target_id=search, key='Enter'))).ok
        assert await browser.active.locator('#result').inner_text() == 'No results'
        sequential = action_for(obs, 'type', target_id=search, text='running shoes', input_mode='sequential')
        assert (await executor.execute(sequential)).ok
        assert await browser.active.locator('input').input_value() == 'running shoes'
        assert (await executor.execute(action_for(obs, 'key_press', target_id=search, key='Enter'))).ok
        assert await browser.active.locator('#result').inner_text() == 'Results for running shoes'


@pytest.mark.asyncio
async def test_sequential_input_uses_u_forced_fill_without_extra_control_policy():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '<input aria-label="Search">')
        obs, registry = await observe(browser)
        executor.publish(registry)
        sequential = action_for(obs, 'type', target_id=target_id(obs, 'input_elements', 'Search'), text='shoes', input_mode='sequential')
        await browser.active.locator('input').evaluate("e => e.type = 'password'")
        assert (await executor.execute(sequential)).ok
        assert await browser.active.locator('input').input_value() == 'shoes'
        await browser.active.locator('input').evaluate("e => {e.type = 'text'; e.readOnly = true}")
        assert (await executor.execute(sequential)).ok
        await browser.active.locator('input').evaluate("e => {e.readOnly = false; e.disabled = true}")
        assert (await executor.execute(sequential)).ok
        assert await browser.active.locator('input').input_value() == 'shoes'


@pytest.mark.asyncio
async def test_search_enter_scroll_and_observation_id_is_not_an_execution_gate():
    async with BrowserSession(False, 800, 400) as browser:
        executor = await setup_page(browser, '''<input aria-label="Search" onkeydown="if(event.key==='Enter') document.querySelector('h1').textContent=this.value">
            <h1>Waiting</h1><div style="height:650px"></div><button>Offscreen filter</button>''')
        obs, registry = await observe(browser)
        executor.publish(registry)
        search = target_id(obs, 'input_elements', 'Search')
        assert (await executor.execute(action_for(obs, 'type', target_id=search, text='running shoes'))).ok
        assert (await executor.execute(action_for(obs, 'key_press', target_id=search, key='Enter'))).ok
        assert await browser.active.locator('h1').inner_text() == 'running shoes'
        assert any(e.name == 'Offscreen filter' for e in obs.clickable_elements)
        assert (await executor.execute(action_for(obs, 'scroll', scroll_y=600))).ok
        fresh, registry = await observe(browser)
        executor.publish(registry)
        assert any(e.name == 'Offscreen filter' for e in fresh.clickable_elements)
        stale = await executor.execute(action_for(obs, 'scroll', scroll_y=-600))
        assert stale.ok
        assert (await executor.execute(action_for(fresh, 'scroll', scroll_y=-600))).ok
        assert await browser.active.evaluate('scrollY') == 0


@pytest.mark.asyncio
async def test_custom_roles_click_disabled_readonly_and_native_select():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '''
            <div role="checkbox" aria-label="In stock" aria-checked="false" tabindex="0" onclick="this.setAttribute('aria-checked','true')">Stock</div>
            <div role="radio" aria-label="Small" tabindex="0">Small</div>
            <div role="combobox" aria-label="Category" tabindex="0">Category</div>
            <div role="option" aria-label="Shoes" tabindex="0">Shoes</div>
            <div role="menuitem" aria-label="Sort price" tabindex="0">Price</div>
            <div role="checkbox" aria-label="Disabled stock" aria-disabled="true" tabindex="0">Disabled</div>
            <input aria-label="Readonly" readonly value="fixed">
            <input aria-label="Password" type="password">
            <select aria-label="Color"><option value="a">Same</option><option value="b">Same</option></select>''')
        obs, registry = await observe(browser)
        executor.publish(registry)
        by_name = {e.name:e for e in obs.clickable_elements}
        assert {'In stock', 'Small', 'Shoes', 'Disabled stock'} <= by_name.keys()
        assert 'Sort price' not in by_name
        assert 'Category' not in by_name
        assert not by_name['Disabled stock'].enabled
        assert not any(e.name in {'Readonly', 'Password'} for e in obs.input_elements)
        assert any(e.name == 'Color' for e in obs.clickable_elements)
        assert [e.name for e in obs.select_elements] == ['Color']
        assert (await executor.execute(action_for(obs, 'click', target_id=by_name['In stock'].id))).ok
        fresh, registry = await observe(browser)
        executor.publish(registry)
        assert next(e for e in fresh.clickable_elements if e.name == 'In stock').checked is True
        disabled = await executor.execute(action_for(fresh, 'click', target_id=next(e.id for e in fresh.clickable_elements if e.name == 'Disabled stock')))
        assert not disabled.ok  # Playwright may fail an obscured or non-interactable element.
        password_id = next(e.id for e in fresh.clickable_elements if e.name == 'Password')
        password = await executor.execute(action_for(fresh, 'key_press', target_id=password_id, key='Enter'))
        assert password.ok
        unsupported = await executor.execute(action_for(fresh, 'select', target_id='category', option_value='a'))
        assert unsupported.error['code'] == 'target_not_found'
        color = target_id(fresh, 'select_elements', 'Color')
        assert (await executor.execute(action_for(fresh, 'select', target_id=color, option_value='b'))).ok


@pytest.mark.asyncio
async def test_key_press_resolves_dom_target_without_tab_or_origin_gates():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '<h1>Heading</h1><button>Submit</button><input aria-label="Search">')
        obs, registry = await observe(browser)
        executor.publish(registry)
        result = await executor.execute(action_for(obs, 'key_press', target_id='heading', key='Enter'))
        assert result.error['code'] == 'target_not_found'
        wrong_tab = action_for(obs, 'scroll', scroll_y=100).model_copy(update={'tab_id':'tab-2'})
        assert (await executor.execute(wrong_tab)).ok
        executor.allowed_origins = ['https://elsewhere.test']
        assert (await executor.execute(action_for(obs, 'scroll', scroll_y=100))).ok
        assert (await executor.execute(action_for(obs, 'key_press', target_id=target_id(obs, 'input_elements', 'Search'), key='Control+A'))).ok


@pytest.mark.asyncio
async def test_scroll_does_not_require_study_opt_in():
    async with BrowserSession(False, 800, 400) as browser:
        await setup_page(browser, '<h1>Page</h1><div style="height:2000px"></div>')
        executor = ActionExecutor(browser, ['https://shop.test'])
        obs, registry = await observe(browser)
        executor.publish(registry)
        result = await executor.execute(action_for(obs, 'scroll', scroll_y=600))
        assert result.ok
        assert await browser.active.evaluate('scrollY') > 0


@pytest.mark.asyncio
async def test_space_toggles_checkbox_and_keyboard_navigation_can_cross_origin():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '<input type="checkbox" aria-label="Stock"><a href="https://outside.invalid/">Outside</a>')
        await browser.context.route('https://outside.invalid/**', lambda route: route.fulfill(body='<title>outside</title><p>external</p>', content_type='text/html'))
        obs, registry = await observe(browser)
        executor.publish(registry)
        assert (await executor.execute(action_for(obs, 'key_press', target_id=target_id(obs, 'input_elements', 'Stock'), key='Space'))).ok
        assert await browser.active.locator('input').is_checked()
        obs, registry = await observe(browser)
        executor.publish(registry)
        result = await executor.execute(action_for(obs, 'key_press', target_id='outside', key='Enter'))
        assert result.ok
        assert browser.active.url.startswith('https://outside.invalid/')


@pytest.mark.asyncio
async def test_type_can_target_password_and_playwright_reports_readonly_errors():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '<input aria-label="Search"><button>Submit</button>')
        obs, registry = await observe(browser)
        executor.publish(registry)
        await browser.active.locator('input').evaluate("e => e.type = 'password'")
        search = target_id(obs, 'input_elements', 'Search')
        result = await executor.execute(action_for(obs, 'type', target_id=search, text='secret'))
        assert result.ok
        assert await browser.active.locator('input').input_value() == 'secret'
        await browser.active.locator('input').evaluate("e => {e.type = 'text'; e.readOnly = true}")
        result = await executor.execute(action_for(obs, 'type', target_id=search, text='change'))
        assert result.ok  # U uses forced fill; Playwright accepts this readonly fixture.
        assert await browser.active.locator('input').input_value() == 'secret'
        await browser.active.locator('button').evaluate('e => e.remove()')
        result = await executor.execute(action_for(obs, 'key_press', target_id=target_id(obs, 'clickable_elements', 'Submit'), key='Enter'))
        assert result.error['code'] == 'target_not_found'


@pytest.mark.asyncio
@pytest.mark.parametrize('claim', ['completed', 'give_up'])
@pytest.mark.parametrize('confidence', [.95, .1])
async def test_jev_finish_candidate_and_fallback_preserve_outcomes(claim, confidence):
    class Provider:
        model = 'jev-test'
        async def choose(self, state, candidates):
            self.candidate = next(c for c in candidates if c.get('finish', {}).get('claim') == claim)
            return self.candidate['id'], confidence, {}, {'input_tokens':1, 'output_tokens':1}
        async def complete(self, messages, *args):
            stage=messages[0]['content'].split('FAST_STAGE:',1)[1].splitlines()[0]
            if stage=='perception':return json.dumps({'perception':'현재 화면을 확인합니다.'}), {'input_tokens':1, 'output_tokens':1}
            if stage=='plan':return json.dumps({'plan':'과업을 진행합니다.'}), {'input_tokens':1, 'output_tokens':1}
            assert confidence < .65
            return json.dumps({'candidate_id':self.candidate['id'],'rationale_summary':'종료 후보를 선택합니다.'}), {'input_tokens':1, 'output_tokens':1}
    obs = Observation(observation_id='o', tab_id='t', url='https://shop.test', title='', html='')
    persona = Persona(persona_id='p', background='b', digital_familiarity='normal', preferences=['x'], intent='task')
    result = await FastLoop(Provider(), BudgetManager(4, 10000), 'test', .2, 100).decide(persona, 'task', obs, [])
    assert result.action is None
    assert result.finish.claim == claim


def test_jev_candidate_order_options_and_bounded_finish_capacity():
    obs = Observation(observation_id='o', tab_id='t', url='https://shop.test', title='', html='',
        clickable_elements=[ElementInfo(id='first', role='button', name='First'), ElementInfo(id='second', role='button', name='Second')],
        select_elements=[ElementInfo(id='color', role='combobox', name='Color', options=[{'value':'a','label':'Same'}, {'value':'b','label':'Same'}])])
    candidates = FastLoop._candidates(obs, 'task')
    assert [c['id'] for c in candidates[:4]] == ['click:first', 'click:second', 'select:color:0', 'select:color:1']
    assert len({c['id'] for c in candidates}) == len(candidates)
    assert {c['finish']['claim'] for c in candidates if c.get('finish')} == {'completed', 'give_up'}
    obs.clickable_elements *= 200
    candidates = FastLoop._candidates(obs, 'task')
    assert len(candidates) <= 255
    assert {c['finish']['claim'] for c in candidates if c.get('finish')} == {'completed', 'give_up'}
