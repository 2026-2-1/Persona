import json
import asyncio
from pathlib import Path

import pytest

from uxagent.offline import OfflineStudy, run_scenario
from uxagent.reports import build_cards

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def deadline_runtime(monkeypatch):
    """Isolate run deadlines from Chromium startup and shared fixture contention."""
    import uxagent.offline as offline
    from uxagent.observation import TargetRegistry
    from uxagent.schemas import ActionResult, CaptureInfo, ElementInfo, Observation

    class Page:
        url = ''
        async def goto(self, url, **kwargs):self.url = url
        async def wait_for_load_state(self, *args, **kwargs):pass

    class Browser:
        def __init__(self, *args):self.active = Page()
        async def __aenter__(self):return self
        async def __aexit__(self, *args):pass
        async def set_allowed_origins(self, *args):pass

    class Executor:
        def __init__(self, *args, **kwargs):pass
        def publish(self, registry):pass
        async def execute(self, action):
            return ActionResult(action_id='synthetic-action', observation_id=action.observation_id,
                ok=True, url_before='http://127.0.0.1/', url_after='http://127.0.0.1/', elapsed_ms=1)

    async def capture(browser, folder, **kwargs):
        identifier = 'synthetic-observation'
        image = f'observations/{identifier}.png'
        observation = Observation(observation_id=identifier, tab_id='tab-1', url=browser.active.url,
            title='Synthetic deadline capture', html='<input aria-label="상품 검색">',
            input_elements=[ElementInfo(id='query', role='textbox', name='상품 검색')],
            capture=CaptureInfo(screenshot_path=image))
        (folder/'observations').mkdir(exist_ok=True)
        # Valid one-pixel PNG used only as an injected synthetic capture.
        (folder/image).write_bytes(bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000b49444154789c636000020000050001a5f645400000000049454e44ae426082'))
        offline.write_json(folder/f'observations/{identifier}.json', observation.model_dump())
        return observation, TargetRegistry(identifier, 'tab-1', {}, {browser.active.url})

    async def allowed(*args):return True
    monkeypatch.setattr(offline, 'BrowserSession', Browser)
    monkeypatch.setattr(offline, 'ActionExecutor', Executor)
    monkeypatch.setattr(offline, 'observe', capture)
    monkeypatch.setattr(offline, 'readonly_policy', allowed)
    return Browser


@pytest.mark.asyncio
@pytest.mark.parametrize('step_type', ['type', 'check'])
async def test_final_checkpoint_cannot_outlive_run_deadline(tmp_path, monkeypatch, deadline_runtime, step_type):
    import uxagent.offline as offline
    finished = False
    async def late_checkpoint(*args):
        nonlocal finished
        await asyncio.sleep(2)
        finished = True
        return {'verification':'success', 'reason':'late success',
                'feature_checks':[{'id':'search', 'label':'Search', 'status':'pass'}]}
    monkeypatch.setattr(offline, 'checkpoint', late_checkpoint)
    step = {'label':'Final search checkpoint', 'type':step_type, 'check':'search'}
    if step_type == 'type':
        step.update(target_name='상품 검색', text='러닝화')
    config = tmp_path/'deadline.json'
    config.write_text(json.dumps({'study_id':'deadline', 'task':'search', 'fixture':'decathlon.html',
        'run_timeout_seconds':1, 'steps':[step]}), encoding='utf-8')
    folder, summary = await run_scenario(config, output_root=tmp_path/'runs')
    assert summary['termination_reason'] == 'run_timeout'
    assert summary['verification'] == 'unknown'
    assert not finished
    assert summary['last_error']['code'] == 'run_timeout'
    records = [json.loads(line) for line in (folder/'steps.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(records) == 1
    assert records[0]['verification'] == 'unknown'
    assert records[0]['error']['code'] == 'run_timeout'
    assert records[0]['observation_id']
    assert list((folder/'observations').glob('*.png'))
    if step_type == 'type':
        assert summary['action_attempts'] == 1
        assert records[0]['action']['text'] == '러닝화'
        assert records[0]['result']['ok']
        assert records[0]['next_observation_id'] is None
        assert summary['metrics']['recording']['rate'] < 1


@pytest.mark.asyncio
async def test_deadline_during_action_keeps_attempt_without_inventing_result(tmp_path, monkeypatch, deadline_runtime):
    import uxagent.offline as offline
    async def delayed_execute(*args):
        await asyncio.sleep(2)
        raise AssertionError('execution should be cancelled at the run deadline')
    monkeypatch.setattr(offline.ActionExecutor, 'execute', delayed_execute)
    config = tmp_path/'action-deadline.json'
    config.write_text(json.dumps({'study_id':'action-deadline', 'task':'search', 'fixture':'decathlon.html',
        'run_timeout_seconds':1, 'steps':[{'label':'Enter query', 'type':'type', 'target_name':'상품 검색', 'text':'러닝화'}]}), encoding='utf-8')
    folder, summary = await run_scenario(config, output_root=tmp_path/'runs')
    assert summary['termination_reason'] == 'run_timeout'
    assert summary['verification'] == 'unknown'
    assert summary['action_attempts'] == 1
    assert summary['action_successes'] == 0
    records = [json.loads(line) for line in (folder/'steps.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(records) == 1
    assert records[0]['action']['text'] == '러닝화'
    assert records[0]['result'] is None
    assert records[0]['observation_id']
    assert records[0]['error']['code'] == 'run_timeout'
    assert summary['metrics']['recording']['attempted'] == 1
    assert summary['metrics']['recording']['unrecorded'] == 0
    assert summary['metrics']['recording']['rate'] == 0


@pytest.mark.asyncio
async def test_deadline_cleans_partial_browser_startup(tmp_path, monkeypatch, deadline_runtime):
    import uxagent.offline as offline
    cleanup = []
    class SlowBrowser(deadline_runtime):
        async def __aenter__(self):
            await asyncio.sleep(2)
            return self
        async def __aexit__(self, *args):cleanup.append('closed')
    monkeypatch.setattr(offline, 'BrowserSession', SlowBrowser)
    config = tmp_path/'startup-deadline.json'
    config.write_text(json.dumps({'study_id':'startup-deadline', 'task':'search', 'fixture':'decathlon.html',
        'run_timeout_seconds':1, 'steps':[{'label':'Query', 'type':'type', 'target_name':'상품 검색', 'text':'러닝화'}]}), encoding='utf-8')
    _, summary = await run_scenario(config, output_root=tmp_path/'runs')
    assert summary['termination_reason'] == 'run_timeout'
    assert summary['action_attempts'] == 0
    assert cleanup == ['closed']


@pytest.mark.asyncio
async def test_offline_flow_never_requests_a_model_and_preserves_checkpoints(tmp_path,monkeypatch):
    import uxagent.llm as llm
    async def forbidden(*args,**kwargs):
        raise AssertionError('offline scenario must not call a model')
    for name in ('MockProvider','OpenAIProvider','ClaudeProvider','GeminiProvider','JevProvider'):
        monkeypatch.setattr(getattr(llm,name),'complete',forbidden)
    monkeypatch.setattr(llm.JevProvider,'choose',forbidden)
    folder,summary=await run_scenario(ROOT/'configs/scenarios/decathlon-flow.json',output_root=tmp_path)
    assert summary['verification']=='success'
    assert summary['llm_request_count']==0
    assert summary['execution_mode']=='scripted'
    assert summary['source_kind']=='synthetic_fixture'
    assert summary['cost']==0
    assert summary['metrics']['recording']['rate']==1
    assert {c['task_id'] for c in summary['evaluator']['feature_checks']}=={'search','filters','detail'}
    assert (folder/'llm_calls.jsonl').read_text(encoding='utf-8')==''


@pytest.mark.asyncio
async def test_failure_card_links_the_failed_check_not_last_unrelated_step(tmp_path):
    folder,summary=await run_scenario(ROOT/'configs/scenarios/decathlon-flow.json',output_root=tmp_path,defect='filter')
    assert summary['verification']=='failure'
    steps=[json.loads(line) for line in (folder/'steps.jsonl').read_text(encoding='utf-8').splitlines()]
    detail={'run':json.loads((folder/'run.json').read_text(encoding='utf-8')),'summary':summary,'steps':steps}
    cards=build_cards(detail)
    card=next(c for c in cards if c.get('task_id')=='filters')
    assert card['evidence_step_ids']==[6]
    assert card['classification']=='unmet_checkpoint'
    assert '가격' in card['recommendation'] or '필터' in card['recommendation']


def test_external_scenario_requires_explicit_origin_and_profile():
    with pytest.raises(ValueError):
        OfflineStudy.model_validate({'study_id':'unsafe','task':'search','start_url':'https://evil.test','steps':[{'label':'scroll','type':'scroll','scroll_y':200}]})


@pytest.mark.asyncio
async def test_readonly_policy_blocks_purchase_and_identity_fields():
    from uxagent.offline import readonly_policy
    from uxagent.schemas import Action
    from uxagent.browser import BrowserSession
    from uxagent.observation import observe
    async with BrowserSession(False) as browser:
        await browser.active.set_content('<button id="buy" aria-label="바로 구매">바로 구매</button><input type="email" aria-label="이메일"><input aria-label="상품 검색">')
        observation,registry=await observe(browser)
        target=next(x.id for x in observation.clickable_elements if x.name=='바로 구매')
        assert not await readonly_policy(Action(type='click',target_id=target,observation_id=observation.observation_id,tab_id=observation.tab_id),registry)
        email=next(x.id for x in observation.input_elements if x.name=='이메일')
        assert not await readonly_policy(Action(type='type',target_id=email,text='not-transmitted',observation_id=observation.observation_id,tab_id=observation.tab_id),registry)
        query=next(x.id for x in observation.input_elements if x.name=='상품 검색')
        assert await readonly_policy(Action(type='type',target_id=query,text='가방',observation_id=observation.observation_id,tab_id=observation.tab_id),registry)
