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


def test_explicit_scroll_and_bounded_actions_schema():
    assert StudyConfig(study_id='s', start_url='https://shop.test', task='search',
                       allowed_origins=['https://shop.test'], explicit_scroll=True).explicit_scroll
    for key in ['Enter', 'Escape', 'Tab', 'ArrowUp', 'ArrowDown', 'Space']:
        assert Action(type='keypress', observation_id='o', tab_id='t', target_id='search', key=key).key == key
    for distance in [-900, -1, 1, 900]:
        assert Action(type='scroll', observation_id='o', tab_id='t', scroll_y=distance).scroll_y == distance


@pytest.mark.parametrize('fields', [
    {'type':'keypress', 'key':'Enter'},
    {'type':'keypress', 'target_id':'search', 'key':'Control+A'},
    {'type':'keypress', 'target_id':'search', 'key':'Enter', 'text':'script'},
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
    {'type':'keypress', 'target_id':'search', 'key':'Enter', 'input_mode':'fill'},
    {'type':'scroll', 'scroll_y':100, 'input_mode':'sequential'},
    {'type':'type', 'target_id':'search', 'text':'shoes', 'input_mode':'script'},
])
def test_input_mode_is_an_explicit_type_only_option(fields):
    with pytest.raises(ValidationError):
        Action(observation_id='o', tab_id='t', **fields)


async def setup_page(browser, markup):
    await browser.set_allowed_origins(['https://shop.test'])
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
        default_input = action_for(obs, 'type', target_id='search', text='running shoes')
        assert (await executor.execute(default_input)).ok
        assert (await executor.execute(action_for(obs, 'keypress', target_id='search', key='Enter'))).ok
        assert await browser.active.locator('#result').inner_text() == 'No results'
        sequential = action_for(obs, 'type', target_id='search', text='running shoes', input_mode='sequential')
        assert (await executor.execute(sequential)).ok
        assert await browser.active.locator('input').input_value() == 'running shoes'
        assert (await executor.execute(action_for(obs, 'keypress', target_id='search', key='Enter'))).ok
        assert await browser.active.locator('#result').inner_text() == 'Results for running shoes'


@pytest.mark.asyncio
async def test_sequential_input_still_rejects_password_readonly_and_disabled_targets():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '<input aria-label="Search">')
        obs, registry = await observe(browser)
        executor.publish(registry)
        sequential = action_for(obs, 'type', target_id='search', text='shoes', input_mode='sequential')
        await browser.active.locator('input').evaluate("e => e.type = 'password'")
        assert (await executor.execute(sequential)).error['code'] == 'unsupported_control'
        await browser.active.locator('input').evaluate("e => {e.type = 'text'; e.readOnly = true}")
        assert (await executor.execute(sequential)).error['code'] == 'unsupported_control'
        await browser.active.locator('input').evaluate("e => {e.readOnly = false; e.disabled = true}")
        assert (await executor.execute(sequential)).error['code'] == 'not_interactable'
        assert await browser.active.locator('input').input_value() == ''


@pytest.mark.asyncio
async def test_search_enter_scroll_and_stale_observation():
    async with BrowserSession(False, 800, 400) as browser:
        executor = await setup_page(browser, '''<input aria-label="Search" onkeydown="if(event.key==='Enter') document.querySelector('h1').textContent=this.value">
            <h1>Waiting</h1><div style="height:650px"></div><button>Offscreen filter</button>''')
        obs, registry = await observe(browser)
        executor.publish(registry)
        assert (await executor.execute(action_for(obs, 'type', target_id='search', text='running shoes'))).ok
        assert (await executor.execute(action_for(obs, 'keypress', target_id='search', key='Enter'))).ok
        assert await browser.active.locator('h1').inner_text() == 'running shoes'
        assert not any(e.name == 'Offscreen filter' for e in obs.clickable_elements)
        assert (await executor.execute(action_for(obs, 'scroll', scroll_y=600))).ok
        fresh, registry = await observe(browser)
        executor.publish(registry)
        assert any(e.name == 'Offscreen filter' for e in fresh.clickable_elements)
        stale = await executor.execute(action_for(obs, 'scroll', scroll_y=-600))
        assert stale.error['code'] == 'stale_observation'
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
        assert {'In stock', 'Small', 'Category', 'Shoes', 'Sort price', 'Disabled stock'} <= by_name.keys()
        assert not by_name['Disabled stock'].enabled
        assert not any(e.name in {'Readonly', 'Password'} for e in obs.input_elements)
        assert not any(e.name == 'Color' for e in obs.clickable_elements)
        assert [e.name for e in obs.select_elements] == ['Color']
        assert (await executor.execute(action_for(obs, 'click', target_id='in.stock'))).ok
        fresh, registry = await observe(browser)
        executor.publish(registry)
        assert next(e for e in fresh.clickable_elements if e.name == 'In stock').checked is True
        disabled = await executor.execute(action_for(fresh, 'click', target_id='disabled.stock'))
        assert disabled.error['code'] == 'not_interactable'
        # Password remains forbidden even when an unexpected registry exposes click capability.
        registry.targets['password'].capabilities.add('click')
        password = await executor.execute(action_for(fresh, 'keypress', target_id='password', key='Enter'))
        assert password.error['code'] == 'unsupported_control'
        unsupported = await executor.execute(action_for(fresh, 'select', target_id='category', option_value='a'))
        assert unsupported.error['code'] == 'unsupported_control'
        assert (await executor.execute(action_for(fresh, 'select', target_id='color', option_value='b'))).ok


@pytest.mark.asyncio
async def test_keypress_requires_capability_and_current_tab_and_origin():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '<h1>Heading</h1><button>Submit</button><input aria-label="Search">')
        obs, registry = await observe(browser)
        executor.publish(registry)
        result = await executor.execute(action_for(obs, 'keypress', target_id='heading', key='Enter'))
        assert result.error['code'] == 'unsupported_control'
        await browser.active.locator('button').evaluate("e => e.setAttribute('aria-disabled', 'true')")
        result = await executor.execute(action_for(obs, 'keypress', target_id='submit', key='Space'))
        assert result.error['code'] == 'not_interactable'
        wrong_tab = action_for(obs, 'scroll', scroll_y=100).model_copy(update={'tab_id':'tab-2'})
        assert (await executor.execute(wrong_tab)).error['code'] == 'stale_observation'
        executor.allowed_origins = ['https://elsewhere.test']
        assert (await executor.execute(action_for(obs, 'scroll', scroll_y=100))).error['code'] == 'navigation_blocked'
        assert (await executor.execute(action_for(obs, 'keypress', target_id='search', key='Enter'))).error['code'] == 'navigation_blocked'


@pytest.mark.asyncio
async def test_scroll_requires_explicit_opt_in():
    async with BrowserSession(False, 800, 400) as browser:
        await setup_page(browser, '<h1>Page</h1><div style="height:2000px"></div>')
        executor = ActionExecutor(browser, ['https://shop.test'])
        obs, registry = await observe(browser)
        executor.publish(registry)
        result = await executor.execute(action_for(obs, 'scroll', scroll_y=600))
        assert result.error['code'] == 'unsupported_control'
        assert await browser.active.evaluate('scrollY') == 0


@pytest.mark.asyncio
async def test_space_toggles_checkbox_and_keyboard_navigation_is_blocked():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '<input type="checkbox" aria-label="Stock"><a href="https://outside.invalid/">Outside</a>')
        obs, registry = await observe(browser)
        executor.publish(registry)
        assert (await executor.execute(action_for(obs, 'keypress', target_id='stock', key='Space'))).ok
        assert await browser.active.locator('input').is_checked()
        obs, registry = await observe(browser)
        executor.publish(registry)
        result = await executor.execute(action_for(obs, 'keypress', target_id='outside', key='Enter'))
        assert not result.ok
        assert result.error['code'] == 'navigation_blocked'
        # Chromium can replace a blocked navigation with its internal error page.
        assert not browser.active.url.startswith('https://outside.invalid')
        assert browser.blocked_navigations == ['https://outside.invalid/']


@pytest.mark.asyncio
async def test_live_target_changes_cannot_enable_password_or_readonly_input():
    async with BrowserSession(False) as browser:
        executor = await setup_page(browser, '<input aria-label="Search"><button>Submit</button>')
        obs, registry = await observe(browser)
        executor.publish(registry)
        await browser.active.locator('input').evaluate("e => e.type = 'password'")
        result = await executor.execute(action_for(obs, 'keypress', target_id='search', key='Enter'))
        assert result.error['code'] == 'unsupported_control'
        await browser.active.locator('input').evaluate("e => {e.type = 'text'; e.readOnly = true}")
        result = await executor.execute(action_for(obs, 'type', target_id='search', text='change'))
        assert result.error['code'] == 'unsupported_control'
        await browser.active.locator('button').evaluate('e => e.remove()')
        result = await executor.execute(action_for(obs, 'keypress', target_id='submit', key='Enter'))
        assert result.error['code'] == 'target_detached'


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
            assert confidence < .65
            return json.dumps({'candidate_id':self.candidate['id']}), {'input_tokens':1, 'output_tokens':1}
    obs = Observation(observation_id='o', tab_id='t', url='https://shop.test', title='', html='')
    persona = Persona(persona_id='p', background='b', digital_familiarity='normal', preferences=['x'], intent='task')
    result = await FastLoop(Provider(), BudgetManager(3, 10000), 'test', .2, 100).decide(persona, 'task', obs, [])
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
