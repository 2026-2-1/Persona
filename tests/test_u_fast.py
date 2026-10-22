"""Issue #83: U request contracts, shared-memory order and proposal provenance."""
import asyncio
import json
from pathlib import Path

import pytest

from uxagent.brain import Brain
from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager, BudgetExceeded
from uxagent.memory import MemoryStore
from uxagent.schemas import Observation, Persona, ElementInfo


class Writer:
    def __init__(self):
        self.rows = []

    def write(self, row):
        self.rows.append(row)


class Slow:
    def __init__(self):
        self.starts = []

    def start(self, *args, **kwargs):
        self.starts.append(args)

    def pop_completed(self):
        return []


class Provider:
    model = "persona-qwen"

    def __init__(self):
        self.calls = []
        self.overrides = {}

    async def complete(self, messages, model, temperature, max_tokens):
        stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0]
        payload = json.loads(messages[1]["content"])
        self.calls.append((stage, payload, model))
        result = {
            "perception": {"observations": ["전체 페이지 관찰", "두 번째 항목은 소비하지 않음"]},
            "feedback": {"thoughts": ["직전 제안을 다시 확인했다"]},
            "plan": {"plan": "검색 후 결과 확인", "rationale": "검색이 필요하다", "next_step": "검색어 입력"},
            "decision": {"actions": [{"action": "type", "target": "search", "text": "러닝화",
                                       "enter": True, "description": "러닝화 검색"}]},
        }[stage]
        return json.dumps(self.overrides.get(stage, result), ensure_ascii=False), {
            "provider": "gpu", "model": model, "input_tokens": 7, "output_tokens": 3}


def setup(provider=None, mode="persona", request_limit=None):
    provider = provider or Provider()
    memory_writer, stages, tasks = Writer(), Writer(), Writer()
    memory = MemoryStore("run-u", memory_writer)
    persona = Persona(persona_id="p", background="PRIVATE_BACKGROUND", digital_familiarity="PRIVATE_SKILL",
                      preferences=["PRIVATE_PREFERENCE"], constraints={"budget": 80000}, intent="러닝화 찾기")
    calls = []
    fast = FastLoop(provider, BudgetManager(request_limit, None), "persona-qwen", .2, 1200, calls.append)
    slow = Slow()
    brain = Brain(fast, slow, memory, persona, mode, tasks, stage_writer=stages)
    observation = Observation(observation_id="obs-u", tab_id="tab-u", url="https://shop.test",
                              title="Shop", html="<input>Crime security 러닝화</input>",
                              input_elements=[ElementInfo(id="search", role="textbox", name="검색")],
                              clickable_elements=[ElementInfo(id="submit", role="button", name="검색 버튼")])
    queries = []

    async def retrieve(query, mode):
        queries.append((query, mode))
        return [entry.model_dump() for entry in memory.entries]

    return brain, observation, retrieve, provider, memory_writer, stages, tasks, calls, queries


def test_large_gpu_observation_keeps_modal_context_and_dismiss_target():
    from uxagent.schemas import Observation, ElementInfo
    brain, _, _, _, _, _, _, _, _ = setup()
    obs = Observation(observation_id='obs-modal', tab_id='tab-1', url='https://shop.test', title='Shop',
        html='<main>' + '상품 안내 ' * 1800 + '</main><div role="dialog" aria-modal="true">'
             '<div role="dialog" aria-label="Promotional pop-up" aria-modal="true">'
             '<div role="button" aria-label="Close" parser-semantic-id="dismiss"></div>'
             '<p>다가오는 마라톤!</p></div></div>',
        clickable_elements=[ElementInfo(id='dismiss', role='button', name='Close')])
    compact, aliases, originals = brain.fast._model_html(obs, group_text=True)
    assert '<dialogs>' in compact and 'aria-modal="true"' in compact
    assert 'Promotional pop-up' in compact and '다가오는 마라톤!' in compact
    assert f'id="{aliases["dismiss"]}"' in compact.split('</dialogs>')[0]
    assert originals[aliases['dismiss']] == 'dismiss'
    assert compact.count('<dialog ') == 1, 'Nested modal wrappers describe one dialog'


@pytest.mark.asyncio
async def test_first_turn_uses_u_payloads_and_saves_proposals_before_execution():
    brain, obs, retrieve, provider, memories, stages, _, calls, queries = setup()
    decision, sources = await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert [stage for stage, _, _ in provider.calls] == ["perception", "plan", "decision"]
    perceive = provider.calls[0][1]
    assert perceive == obs.html.replace("Crime", "***").replace("security", "***")
    plan_input, act_input = provider.calls[1][1], provider.calls[2][1]
    assert set(plan_input) == {"persona", "intent", "memories", "current_timestamp", "old_plan",
                               "page_context", "interaction_progress"}
    assert plan_input["old_plan"] == "N/A" and plan_input["current_timestamp"] == 0
    assert any("전체 페이지 관찰" in item for item in plan_input["memories"])
    assert queries == [("러닝화 찾기", "fast_plan"), ("검색어 입력", "fast_decision")]
    assert act_input["next_step"] == "검색어 입력"
    assert act_input["environment"] == obs.html
    assert act_input["valid_targets"]["inputs"] == ["search"]
    assert act_input["valid_targets"]["clickable"] == ["submit"]
    assert act_input["valid_targets"]["selects"] == []
    assert [m["kind"] for m in memories.rows] == ["observation", "thought", "plan", "action"]
    assert [m["content_status"] for m in memories.rows] == ["generated"] * 4
    assert memories.rows[-1]["raw_action"]["enter"] is True
    assert all(m["timestamp"] == 0 for m in memories.rows)
    assert brain.memory.timestamp == 1
    assert len(brain.slow.starts) == 1
    assert decision.action.enter is True and decision.action.target_id == "search"
    assert decision.action.observation_id == obs.observation_id
    assert decision.proposed_actions[0].description == "러닝화 검색"
    assert stages.rows[-1]["model_response"]["actions"][0]["target"] == "search"
    assert len(calls) == 3 and all(c["provider"] == "gpu" for c in calls)
    assert [call["method_name"] for call in calls] == ["perceive", "planning", "action"]
    assert all(call["schema_version"] == "2.0" and call["call_id"].startswith("call-") for call in calls)
    assert all(call["recorded_at"].endswith("+00:00") for call in calls)
    assert calls[1]["request"][1]["content"]
    assert json.loads(calls[1]["request"][1]["content"])["memories"]
    assert calls[1]["retrieve_result"]
    assert json.loads(calls[1]["response"])["plan"] == "검색 후 결과 확인"
    assert sources


@pytest.mark.asyncio
async def test_gpu_large_html_uses_short_model_ids_and_restores_action_target():
    brain, obs, _, provider, _, _, _, _, _ = setup()
    target = "search." + "long_path_" * 30
    noisy = "".join(f'<span parser-semantic-id="hover_{i}_' + "path_" * 40 + '" parser-maybe-hoverable="true" parser-hoverable="true">상품</span>' for i in range(120))
    obs.html = f'<html><body>{noisy}<input parser-semantic-id="{target}" placeholder="검색" /></body></html>'
    obs.input_elements = [ElementInfo(id=target, role="textbox", name="검색")]
    obs.clickable_elements = []
    seen = {}

    async def complete(messages, model, temperature, max_tokens):
        stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0]
        payload = json.loads(messages[1]["content"])
        seen[stage] = payload
        if stage == "decision":
            content = {"actions": [{"action": "type", "target": payload["valid_targets"]["inputs"][0],
                                    "text": "러닝화", "description": "검색"}]}
        else:
            content = {"observations": ["상품과 검색창"]}
        return json.dumps(content, ensure_ascii=False), {"provider": "gpu", "model": model,
                                                       "input_tokens": 7, "output_tokens": 3}

    provider.complete = complete
    await brain.fast.perceive_page(obs)
    from uxagent.schemas import UPlan
    proposals = await brain.fast.act(brain.persona, "러닝화", obs, [],
                                     UPlan(plan="검색", rationale="검색", next_step="입력"))
    action, _ = brain.fast.adapt_action(proposals.actions[0], obs)
    assert len(obs.html) > 20000
    assert len(seen["perception"]["content"]) <= 1400
    assert "parser-maybe-hoverable" not in seen["decision"]["environment"]
    assert target not in seen["decision"]["environment"]
    assert seen["decision"]["valid_targets"]["inputs"] == ["s0"]
    assert seen["decision"]["valid_targets"]["clickable"] == []
    assert action.target_id == target
    assert obs.html.endswith(f'<input parser-semantic-id="{target}" placeholder="검색" /></body></html>')


@pytest.mark.asyncio
async def test_gpu_menu_keeps_ancestor_and_sibling_paths_as_action_targets():
    brain, obs, _, provider, _, _, _, _, _ = setup()
    menu = 'running-menu'
    men_shoes = 'men-running-shoes'
    obs.html = ('<html><body><header><a>러닝</a><div parser-semantic-id="running-menu">'
                '<a>러닝 모두 보기</a><div parser-semantic-id="running-shoes">러닝화</div>'
                '<div><a>남성 모두 보기</a><div parser-semantic-id="men-running-shoes">러닝화</div>'
                '<div parser-semantic-id="men-tops">상의</div></div>'
                '<div><a parser-semantic-id="men-view-all">러닝화 모두 보기</a><div parser-semantic-id="road-running">로드러닝/조깅</div>'
                '</div></div></header>' +
                '<span parser-semantic-id="' + 'x' * 9000 + '">상품</span></body></html>')
    obs.clickable_elements = [ElementInfo(id=menu, role='div', name='러닝 메뉴'),
                              ElementInfo(id='men-view-all', role='link', name='러닝화 모두 보기')]
    obs.input_elements = []
    obs.hoverable_elements = [ElementInfo(id='running-shoes', role='div', name='러닝화'),
                              ElementInfo(id=men_shoes, role='div', name='러닝화'),
                              ElementInfo(id='men-tops', role='div', name='상의'),
                              ElementInfo(id='road-running', role='div', name='로드러닝/조깅')]
    compact, aliases, _ = brain.fast._model_html(obs)
    assert 'path="러닝 &gt; 러닝화"' in compact
    assert 'path="러닝 &gt; 남성 &gt; 러닝화"' in compact
    assert 'path="러닝 &gt; 남성 &gt; 상의"' in compact
    assert 'path="러닝 &gt; 남성 &gt; 러닝화 &gt; 로드러닝/조깅"' in compact
    assert aliases[men_shoes] != aliases['running-shoes']
    import re
    parent = re.search(rf'<control id="{aliases[men_shoes]}"[^>]+>', compact).group()
    assert 'expanded="true"' in parent
    assert aliases['road-running'] in parent
    assert 'path="러닝 &gt; 남성 &gt; 러닝화 &gt; 모두 보기"' in compact

    seen = {}

    async def complete(messages, model, temperature, max_tokens):
        seen.update(json.loads(messages[1]['content']))
        return json.dumps({'actions': [{'action': 'click', 'target': aliases[men_shoes],
                                        'description': '남성 러닝화 열기'}]}), {
            'provider': 'gpu', 'model': model, 'input_tokens': 7, 'output_tokens': 3}

    provider.complete = complete
    from uxagent.schemas import UPlan
    proposals = await brain.fast.act(brain.persona, '남성 러닝화', obs, [],
                                     UPlan(plan='러닝 메뉴 탐색', rationale='메뉴 사용', next_step='남성 러닝화 클릭'))
    assert aliases[men_shoes] in seen['valid_targets']['clickable']
    assert proposals.actions[0].target == men_shoes


@pytest.mark.asyncio
async def test_gpu_perception_compacts_visible_content_before_chunking():
    brain, obs, _, provider, _, _, _, calls, _ = setup()
    target = "search." + "very_long_semantic_path_" * 12
    products = [(f"상품{i:03d}", f"{i + 10},000원") for i in range(60)]
    obs.html = ("<main>" + "".join(
        f'<article parser-semantic-id="item.{i}.' + "long_path_" * 12 +
        f'"><h2>{name}</h2><span>{price}</span></article>'
        for i, (name, price) in enumerate(products)) +
        f'<img alt="상품의 옆면 사진"><input parser-semantic-id="{target}" placeholder="검색" value="러닝화"></main>')
    obs.input_elements = [ElementInfo(id=target, role="textbox", name="검색", value="러닝화")]
    obs.clickable_elements = []
    original = obs.html
    seen = []

    async def complete(messages, model, temperature, max_tokens):
        payload = json.loads(messages[1]["content"])
        seen.append(payload)
        return json.dumps({"observations": [f"조각 {payload['chunk_index']}"]}), {
            "provider": "gpu", "model": model, "input_tokens": 7, "output_tokens": 3}

    provider.complete = complete
    await brain.fast.perceive_page(obs)
    source = "".join(item["content"] for item in seen)
    assert len(original) > 8000
    assert len(source) < len(original) // 2
    assert all(name in source and price in source for name, price in products)
    assert "상품000 10,000원\n상품001 11,000원" in source
    assert "상품의 옆면 사진" in source
    assert 'textbox: 검색 value="러닝화"' in source
    assert target not in source and "parser-semantic-id" not in source
    assert obs.html == original
    assert len(calls) == len(seen)


def test_perception_removes_duplicate_control_markup_without_losing_labels_or_values():
    brain, obs, *_ = setup()
    obs.html = '<main>' + ''.join(f'<span data-unused="{"x" * 150}">상품{i}</span>' for i in range(60)) + '</main>'
    obs.clickable_elements = [ElementInfo(id=f'item-{i}', role='link', name=f'후보 상품 {i}') for i in range(38)]
    obs.clickable_elements.append(ElementInfo(id='search', role='textbox', name='상품 검색'))
    obs.input_elements = [ElementInfo(id='search', role='textbox', name='상품 검색', value='러닝화')]
    before = obs.html
    decision_html = brain.fast._model_html(obs)[0]
    perception_html = brain.fast._model_html(obs, group_text=True)[0]
    assert len(brain.fast._chunks(perception_html)) < len(brain.fast._chunks(decision_html))
    assert all(f'후보 상품 {i}' in perception_html for i in range(38))
    assert 'textbox: 상품 검색 value="러닝화"' in perception_html
    assert perception_html.count('상품 검색') == 1
    assert 'kind="clickable"' in decision_html
    assert obs.html == before


@pytest.mark.asyncio
async def test_gpu_large_page_perception_reads_every_chunk_and_merges_until_one():
    brain, obs, _, provider, _, _, _, calls, _ = setup()
    markers = [f"상품{i:03d}" for i in range(300)]
    obs.html = "<main>" + "".join(f"<p>{marker} 상세 설명과 가격 정보가 표시된다.</p>" for marker in markers) + "</main>"
    seen = []

    async def complete(messages, model, temperature, max_tokens):
        payload = json.loads(messages[1]["content"])
        seen.append(payload)
        if not isinstance(payload, dict):
            raise AssertionError("large page must be split into source chunks")
        return json.dumps({"observations": [f"{payload['round']}단계 {payload['chunk_index']}번 " + "가" * 190,
                                            "나" * 190]}), {
            "provider": "gpu", "model": model, "input_tokens": 7, "output_tokens": 3}

    provider.complete = complete
    result = await brain.fast.perceive_page(obs)
    first = [payload for payload in seen if payload["round"] == 1]
    assert len(first) > 1
    assert all(len(payload["content"]) <= 1400 for payload in seen)
    assert "".join(payload["content"] for payload in first) == brain.fast._model_html(obs, group_text=True)[0]
    assert all(marker in "".join(payload["content"] for payload in first) for marker in markers)
    assert len({payload["chunk_index"] for payload in first}) == len(first)
    assert seen[-1]["round"] > 1
    assert len(result.observations) == 1
    assert len(calls) == len(seen)


@pytest.mark.asyncio
async def test_gpu_multiple_chunk_observations_are_kept_without_a_final_model_wait():
    brain, obs, _, provider, _, _, _, calls, _ = setup()
    obs.html = "<main>" + "".join(f"<p>상품{i:03d} 가격</p>" for i in range(700)) + "</main>"
    seen = []

    async def complete(messages, model, temperature, max_tokens):
        payload = json.loads(messages[1]["content"])
        seen.append(payload)
        i = payload["chunk_index"]
        return json.dumps({"observations": [f"조각{i} 상품", f"조각{i} 가격"]}), {
            "provider": "gpu", "model": model, "input_tokens": 7, "output_tokens": 3}

    provider.complete = complete
    result = await brain.fast.perceive_page(obs)
    assert len(seen) > 1
    assert all(payload["round"] == 1 for payload in seen)
    assert result.observations == ["\n".join(
        item for i in range(1, len(seen) + 1) for item in (f"조각{i} 상품", f"조각{i} 가격"))]
    assert len(calls) == len(seen)


@pytest.mark.asyncio
async def test_gpu_chunk_trailing_backtick_uses_valid_json_without_model_repair():
    brain, obs, _, provider, _, _, _, calls, _ = setup()
    obs.html = "<main>" + "".join(f"<p>상품{i:03d} 가격</p>" for i in range(700)) + "</main>"

    async def complete(messages, model, temperature, max_tokens):
        return '{"observations":["상품 가격 확인"]}`\n', {
            "provider": "gpu", "model": model, "input_tokens": 7, "output_tokens": 3}

    provider.complete = complete
    result = await brain.fast.perceive_page(obs)
    assert "상품 가격 확인" in result.observations[0]
    assert len(calls) == len(brain.fast._chunks(brain.fast._model_html(obs, group_text=True)[0]))
    assert all(not call.get("error") for call in calls)
    assert all(call["response"].endswith("`\n") for call in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('malformed', [
    '{"observations": ["상품명과 가격", "검색 버튼"}]\n',
    '{"observations": ["상품명과 가격", "검색 버튼"}\n',
])
async def test_gpu_chunk_known_closing_delimiter_errors_reuse_observations_without_model_repair(malformed):
    brain, obs, _, provider, _, _, _, calls, _ = setup()
    obs.html = "<main>" + "".join(f"<p>상품{i:03d} 가격</p>" for i in range(700)) + "</main>"
    requests = 0

    async def complete(messages, model, temperature, max_tokens):
        nonlocal requests
        requests += 1
        assert len(messages) == 2
        return malformed, {"provider": "gpu", "model": model,
                           "input_tokens": 1015, "output_tokens": 180}

    provider.complete = complete
    result = await brain.fast.perceive_page(obs)
    assert requests == len(calls) == len(brain.fast._chunks(brain.fast._model_html(obs, group_text=True)[0]))
    assert "상품명과 가격\n검색 버튼" in result.observations[0]
    assert all(call["response"] == malformed and not call.get("error") for call in calls)


def test_gpu_chunk_parser_rejects_other_malformed_json():
    with pytest.raises(json.JSONDecodeError):
        FastLoop._parse_gpu_chunk_response('{"observations":["상품명", broken"}]')


@pytest.mark.asyncio
async def test_gpu_chunk_single_observation_string_keeps_content_without_retry():
    brain, obs, _, provider, _, _, _, calls, _ = setup()
    obs.html = '<main>' + ''.join(f'<p>상품{i:03d} 가격</p>' for i in range(700)) + '</main>'
    text = 'Max 가격은 80000이며 적용 여부는 확인되지 않았다.'

    async def complete(messages, model, temperature, max_tokens):
        assert len(messages) == 2
        return json.dumps({'observations': text}, ensure_ascii=False), {
            'provider': 'gpu', 'model': model, 'input_tokens': 10, 'output_tokens': 20}

    provider.complete = complete
    result = await brain.fast.perceive_page(obs)
    assert result.observations == ['\n'.join([text] * len(calls))]
    assert len(calls) == len(brain.fast._chunks(brain.fast._model_html(obs, group_text=True)[0]))
    assert all(not call.get('error') for call in calls)


@pytest.mark.asyncio
async def test_later_feedback_and_perception_share_html_and_run_concurrently():
    brain, obs, retrieve, provider, memories, _, _, _, _ = setup()
    await brain.forward("러닝화 찾기", obs, 1, retrieve)
    original = provider.complete
    arrived = {"feedback": asyncio.Event(), "perception": asyncio.Event()}

    async def gated(messages, *args):
        stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0]
        if stage in arrived:
            arrived[stage].set()
            await arrived["perception" if stage == "feedback" else "feedback"].wait()
        return await original(messages, *args)

    provider.complete = gated
    obs.html = "새 검색 결과 HTML"
    await asyncio.wait_for(brain.forward("러닝화 찾기", obs, 2, retrieve), timeout=2)
    feedback = next(payload for stage, payload, _ in provider.calls if stage == "feedback")
    assert feedback["observation"] == obs.html
    assert feedback["last_action"] == json.dumps(memories.rows[3]["raw_action"], ensure_ascii=False)
    assert feedback["last_plan"] == "검색 후 결과 확인"
    assert provider.calls[-2][1]["old_plan"] == "검색 후 결과 확인"
    assert any("직전 제안을 다시 확인했다" in m for m in provider.calls[-2][1]["memories"])
    assert [payload for stage, payload, _ in provider.calls if stage == "perception"][-1] == obs.html
    assert len(brain.slow.starts) == 1


@pytest.mark.asyncio
async def test_executed_first_proposal_and_failure_reach_all_next_decision_stages():
    from uxagent.schemas import ActionResult
    brain, obs, retrieve, provider, *_ = setup()
    provider.overrides['decision'] = {'actions': [
        {'action': 'click', 'target': 'first', 'description': '실제 시도'},
        {'action': 'click', 'target': 'unexecuted', 'description': '미실행 제안'}]}
    await brain.forward('러닝화 찾기', obs, 1, retrieve)
    result = ActionResult(action_id='actual-1', observation_id=obs.observation_id, ok=False,
        error={'code': 'action_timeout', 'message': 'Popup intercepted click'},
        url_before=obs.url, url_after=obs.url, elapsed_ms=15000)
    brain.record_action_result(result)
    await brain.forward('러닝화 찾기', obs, 2, retrieve)
    feedback = next(p for stage, p, _ in provider.calls if stage == 'feedback')
    assert json.loads(feedback['last_action'])['target'] == 'first'
    assert feedback['last_action_result']['action_id'] == 'actual-1'
    assert feedback['last_action_result']['ok'] is False
    assert feedback['last_action_result']['error']['code'] == 'action_timeout'
    for stage in ('plan', 'decision'):
        payload = [p for s, p, _ in provider.calls if s == stage][-1]
        assert payload['last_action_result'] == result.model_dump(mode='json')
        assert payload['last_action']['target'] == 'first'
        assert 'verification' not in payload['last_action_result']


@pytest.mark.asyncio
async def test_feedback_snapshot_keeps_target_and_focus_values_without_other_control_inventory():
    brain, obs, _, provider, *_ = setup()
    obs.interaction_state = {'search_state':{'results_signature':'unchanged','loading':False},
        'inputs':[{'id':'search','name':'검색','value':'러닝화','focused':False,'enabled':True},
                  {'id':'focused','name':'현재 입력','value':'확인','focused':True,'enabled':True},
                  {'id':'other','name':'무관한 입력','value':'not-in-exact-state','focused':False}],
        'popup':{'name':'안내','modal':True,'text':'page data'}}
    await brain.fast.feedback(brain.persona,json.dumps({'action':'key_press','target':'search','key':'Enter'}),
                              '검색 결과 확인',obs,last_action_result={'ok':True})
    payload = provider.calls[-1][1]
    state = payload['feedback_state']
    assert state['url'] == obs.url and state['search_state']['loading'] is False
    assert [(e['id'],e['value']) for e in state['inputs']] == [('search','러닝화'),('focused','확인')]
    assert state['popup'] == {'name':'안내','modal':True}
    assert payload['last_action_result'] == {'ok':True}


@pytest.mark.asyncio
async def test_plan_receives_current_expanded_menu_not_only_old_plan():
    brain, obs, _, provider, *_ = setup()
    obs.html = ('<header><a>러닝 모두 보기</a><div parser-semantic-id="shoes">러닝화</div>'
        '<div><a>러닝화 모두 보기</a><div parser-semantic-id="men">남성</div></div></header>'
        '<span parser-semantic-id="' + 'x' * 9000 + '">상품</span>')
    obs.hoverable_elements = [ElementInfo(id='shoes', role='div', name='러닝화'),
                              ElementInfo(id='men', role='div', name='남성')]
    await brain.fast.make_plan(brain.persona, '러닝화', [], 1, observation=obs)
    payload = provider.calls[-1][1]
    assert payload['page_context']['url'] == obs.url
    assert 'expanded="true"' in payload['page_context']['navigation']
    assert 'visible_children=' in payload['page_context']['navigation']


@pytest.mark.asyncio
async def test_missing_execution_result_is_not_invented_as_success():
    brain, obs, retrieve, provider, *_ = setup()
    await brain.forward('러닝화 찾기', obs, 1, retrieve)
    await brain.forward('러닝화 찾기', obs, 2, retrieve)
    feedback = next(p for stage, p, _ in provider.calls if stage == 'feedback')
    assert feedback['last_action_result'] is None


@pytest.mark.asyncio
async def test_general_condition_does_not_leak_persona_in_any_u_request():
    brain, obs, retrieve, provider, *_ = setup(mode="general")
    await brain.forward("러닝화 찾기", obs, 1, retrieve)
    await brain.forward("러닝화 찾기", obs, 2, retrieve)
    assert "PRIVATE_" not in json.dumps(provider.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_plan", [{"plan": "x", "rationale": "y"},
                                      {"plan": "x", "rationale": "y", "next_step": []}])
async def test_invalid_plan_is_repaired_with_usage_preserved(bad_plan):
    brain, obs, retrieve, provider, _, _, _, calls, _ = setup()
    provider.overrides["plan"] = bad_plan
    with pytest.raises(RuntimeError, match="model_output_error"):
        await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert len([c for c in calls if c["stage"] == "plan"]) == 2
    assert all(c["input_tokens"] == 7 for c in calls)
    assert all(c["error"] == "model_output_error" for c in calls if c["stage"] == "plan")
    repair_request = next(message["content"] for message in calls[1]["request"]
                          if message["role"] == "user" and "완성할 JSON 템플릿" in message["content"])
    template = json.loads(repair_request.split("완성할 JSON 템플릿:\n", 1)[1])
    assert template == {"plan": "x", "rationale": "y", "next_step": ""}
    assert brain.fast.budget.reserved_tokens == 0


@pytest.mark.asyncio
async def test_invalid_action_retry_sends_blank_required_fields_for_qwen_to_complete():
    brain, obs, retrieve, provider, _, _, _, calls, _ = setup()
    original = provider.complete
    attempts = 0
    invalid = {"actions": [{"action": "type", "target": "search",
                            "text": "러닝화", "enter": False}]}
    repaired = {"actions": [{"action": "type", "target": "search",
                             "text": "러닝화", "enter": False,
                             "description": "검색어를 입력한다."}]}

    async def complete(messages, *args):
        nonlocal attempts
        stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0]
        if stage == "decision":
            attempts += 1
            if attempts == 1:
                return json.dumps(invalid, ensure_ascii=False), {
                    "provider": "gpu", "model": "persona-qwen", "input_tokens": 7, "output_tokens": 3}
            repair = messages[-1]["content"]
            assert "완성할 JSON 템플릿" in repair
            assert '"action": "type"' in repair
            assert '"description": ""' in repair
            assert '"target": "search"' in repair
            return json.dumps(repaired, ensure_ascii=False), {
                "provider": "gpu", "model": "persona-qwen", "input_tokens": 8, "output_tokens": 4}
        return await original(messages, *args)

    provider.complete = complete
    decision, _ = await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert attempts == 2
    assert decision.action.type == "type" and decision.action.target_id == "search"
    assert decision.proposed_actions[0].description == "검색어를 입력한다."
    decision_calls = [call for call in calls if call["stage"] == "decision"]
    assert len(decision_calls) == 2
    assert decision_calls[0]["error"] == "model_output_error"
    assert "error" not in decision_calls[1]
    assert brain.fast.budget.reserved_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('correction', ['type', 'raw_type', 'invalid'])
async def test_raw_type_target_retry_explains_formats_and_requires_model_choice(correction):
    brain, obs, retrieve, provider, _, _, _, calls, _ = setup()
    original = provider.complete
    attempts = 0
    invalid = {'actions': [{'action': 'raw_type', 'target': 'search', 'text': '80000',
                            'description': '최대 가격을 입력합니다.'}]}

    async def complete(messages, *args):
        nonlocal attempts
        stage = messages[0]['content'].split('FAST_STAGE:', 1)[1].splitlines()[0]
        if stage != 'decision':
            return await original(messages, *args)
        attempts += 1
        if attempts == 1:
            response = invalid
        else:
            repair = messages[-1]['content']
            template = json.loads(repair.split('완성할 JSON 템플릿:\n', 1)[1])
            assert template['actions'][0] == {'action': 'raw_type', 'description': '최대 가격을 입력합니다.',
                                               'text': '80000'}
            assert 'unexpected_fields' in repair and 'target' in repair
            assert '"action": "type"' in repair and '"target": "search"' in repair
            assert '포커스' in repair
            assert messages[-2]['content'] == json.dumps(invalid, ensure_ascii=False)
            if correction == 'invalid':
                response = invalid
            elif correction == 'type':
                response = {'actions': [{**invalid['actions'][0], 'action': 'type'}]}
            else:
                response = {'actions': [{key: value for key, value in invalid['actions'][0].items() if key != 'target'}]}
        return json.dumps(response, ensure_ascii=False), {
            'provider': 'gpu', 'model': 'persona-qwen', 'input_tokens': 7, 'output_tokens': 3}

    provider.complete = complete
    if correction == 'invalid':
        with pytest.raises(RuntimeError, match='unexpected arguments for raw_type'):
            await brain.forward('최대 가격 입력', obs, 1, retrieve)
    else:
        decision, _ = await brain.forward('최대 가격 입력', obs, 1, retrieve)
        assert decision.action.type == correction
        assert decision.action.target_id == ('search' if correction == 'type' else None)
        assert decision.action.text == '80000'
    decision_calls = [c for c in calls if c['stage'] == 'decision']
    assert attempts == len(decision_calls) == 2
    assert decision_calls[0]['error'] == 'model_output_error'
    assert bool(decision_calls[1].get('error')) == (correction == 'invalid')
    assert brain.fast.budget.reserved_tokens == 0


def test_action_retry_blanks_missing_numeric_arguments_instead_of_inventing_coordinates():
    from uxagent.schemas import UActions

    raw = {'actions': [{'action': 'mouse_click', 'at_y': 250, 'description': '클릭'}]}
    request = FastLoop._repair_request('decision', json.dumps(raw), UActions, 'missing arguments', {})
    template = json.loads(request.split('완성할 JSON 템플릿:\n', 1)[1])
    assert template['actions'][0] == {'action': 'mouse_click', 'at_x': None, 'at_y': 250, 'description': '클릭'}


@pytest.mark.asyncio
async def test_malformed_qwen_action_retry_includes_schema_template_and_original_response():
    brain, obs, retrieve, provider, _, _, _, calls, _ = setup()
    original = provider.complete
    attempts = 0
    malformed = '{"actions":[{"action":"type","target":"search","text":"러닝화","enter=false}]}'
    repaired = {"actions": [{"action": "type", "target": "search", "text": "러닝화",
                             "enter": False, "description": "검색어를 입력한다."}]}

    async def complete(messages, *args):
        nonlocal attempts
        stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0]
        if stage == "decision":
            attempts += 1
            if attempts == 1:
                return malformed, {"provider": "gpu", "model": "persona-qwen", "input_tokens": 7, "output_tokens": 3}
            repair = messages[-1]["content"]
            template_text = repair.split("완성할 JSON 템플릿:\n", 1)[1]
            template = json.loads(template_text)
            assert template == {"actions": [{"action": "", "description": ""}]}
            assert messages[-2] == {"role": "assistant", "content": malformed}
            return json.dumps(repaired, ensure_ascii=False), {
                "provider": "gpu", "model": "persona-qwen", "input_tokens": 8, "output_tokens": 4}
        return await original(messages, *args)

    provider.complete = complete
    decision, _ = await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert attempts == 2
    assert decision.proposed_actions[0].description == "검색어를 입력한다."
    decision_calls = [call for call in calls if call["stage"] == "decision"]
    assert len(decision_calls) == 2 and decision_calls[0]["error"] == "model_output_error"


@pytest.mark.asyncio
async def test_qwen_enter_equals_is_checked_locally_before_action_execution():
    brain, obs, retrieve, provider, _, _, _, calls, _ = setup()
    original = provider.complete
    attempts = 0
    malformed = '{"actions":[{"action":"type","target":"search","text":"러닝화","enter=false"}]}'
    malformed_with_description = ('{"actions":[{"action":"type","target":"search",'
                                  '"text":"러닝화","enter=false","description":"검색어 입력"}]}')

    async def complete(messages, *args):
        nonlocal attempts
        stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0]
        if stage == "decision":
            attempts += 1
            if attempts == 1:
                return malformed, {"provider": "gpu", "model": "persona-qwen",
                                   "input_tokens": 7, "output_tokens": 3}
            repair = messages[-1]["content"]
            template = json.loads(repair.split("완성할 JSON 템플릿:\n", 1)[1])
            assert template["actions"][0] == {"action": "type", "target": "search",
                                               "text": "러닝화", "enter": False,
                                               "description": ""}
            return malformed_with_description, {"provider": "gpu", "model": "persona-qwen",
                                                "input_tokens": 8, "output_tokens": 4}
        return await original(messages, *args)

    provider.complete = complete
    decision, _ = await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert attempts == 2
    assert decision.action.type == "type" and decision.action.target_id == "search"
    decision_calls = [call for call in calls if call["stage"] == "decision"]
    assert decision_calls[0]["response"] == malformed
    assert decision_calls[1]["response"] == malformed_with_description
    assert decision_calls[0]["error"] == "model_output_error"
    assert "error" not in decision_calls[1]
    assert all(call["syntax_repair"] == "enter_boolean_key" for call in decision_calls)


@pytest.mark.asyncio
async def test_empty_observations_fail_without_inventing_a_page():
    brain, obs, retrieve, provider, memories, *_ = setup()
    provider.overrides["perception"] = {"observations": []}
    with pytest.raises(ValueError, match="observations"):
        await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert memories.rows == []


@pytest.mark.asyncio
async def test_empty_actions_fail_and_multiple_proposals_save_all_but_execute_first():
    brain, obs, retrieve, provider, memories, *_ = setup()
    provider.overrides["decision"] = {"actions": []}
    with pytest.raises(RuntimeError, match="model_output_error"):
        await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert not any(m["kind"] == "action" for m in memories.rows)
    provider.overrides["decision"] = {"actions": [
        {"action": "click", "target": "first", "description": "첫 제안"},
        {"action": "click", "target": "second", "description": "둘째 제안"}]}
    decision, _ = await brain.forward("러닝화 찾기", obs, 2, retrieve)
    assert decision.action.target_id == "first"
    assert [m["text"] for m in memories.rows if m["kind"] == "action"] == ["첫 제안", "둘째 제안"]


@pytest.mark.asyncio
async def test_budget_failure_is_not_a_successful_generation():
    brain, obs, retrieve, _, _, _, tasks, calls, _ = setup(request_limit=1)
    with pytest.raises(BudgetExceeded):
        await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert any(r["status"] == "skipped" and r["reason_code"] == "budget_exceeded" for r in tasks.rows)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_failed_parallel_branch_cancels_and_joins_its_sibling():
    brain, obs, retrieve, provider, memories, _, tasks, calls, _ = setup()
    await brain.forward("러닝화 찾기", obs, 1, retrieve)
    perception_started, perception_cancelled = asyncio.Event(), asyncio.Event()

    async def failing(messages, *args):
        stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0]
        if stage == "feedback":
            await perception_started.wait()
            raise RuntimeError("provider_http_400")
        if stage == "perception":
            perception_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                perception_cancelled.set()
        raise AssertionError("Plan and act must not run after a parallel-branch failure")

    provider.complete = failing
    with pytest.raises(RuntimeError, match="provider_http_400"):
        await asyncio.wait_for(brain.forward("러닝화 찾기", obs, 2, retrieve), timeout=2)
    assert perception_cancelled.is_set()
    assert len([m for m in memories.rows if m["kind"] == "action"]) == 1
    assert brain.fast.budget.reserved_tokens == 0
    assert any(r["kind"] == "perception" and r["status"] == "cancelled" for r in tasks.rows)
    assert any(r["kind"] == "feedback" and r["status"] == "failed" for r in tasks.rows)
    assert calls[-1]["error"] == "CancelledError"


@pytest.mark.asyncio
async def test_exhausted_connection_retries_never_send_json_repair(monkeypatch):
    brain, _, _, provider, _, _, _, calls, _ = setup()
    requests = []
    async def refused(messages, *args):
        requests.append(messages.copy())
        raise RuntimeError('provider_transient:ConnectionRefusedError')
    async def no_wait(*args): pass
    provider.complete = refused
    monkeypatch.setattr('uxagent.fast_loop.asyncio.sleep', no_wait)
    with pytest.raises(RuntimeError, match='^provider_transient:ConnectionRefusedError$'):
        await brain.fast._generate('perception', 'Observe', {})
    assert len(requests) == 5
    assert all(len(messages) == 2 for messages in requests)
    assert len(calls) == 5


@pytest.mark.asyncio
async def test_cancelling_parallel_phase_leaves_no_requests_or_tasks_in_flight():
    brain, obs, retrieve, provider, _, _, tasks, _, _ = setup()
    await brain.forward("러닝화 찾기", obs, 1, retrieve)
    both_started = {stage: asyncio.Event() for stage in ("feedback", "perception")}

    async def blocking(messages, *args):
        stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0]
        both_started[stage].set()
        await asyncio.Event().wait()

    provider.complete = blocking
    forward = asyncio.create_task(brain.forward("러닝화 찾기", obs, 2, retrieve))
    await asyncio.wait_for(asyncio.gather(*(event.wait() for event in both_started.values())), timeout=2)
    forward.cancel()
    with pytest.raises(asyncio.CancelledError):
        await forward
    assert not brain.fast_inflight
    assert brain.fast.budget.reserved_tokens == 0
    assert {r["kind"] for r in tasks.rows if r["status"] == "cancelled"} == {"perception", "feedback"}


@pytest.mark.asyncio
async def test_forward_action_is_supported_and_keeps_the_original_proposal():
    brain, obs, retrieve, provider, memories, stages, *_ = setup()
    provider.overrides["decision"] = {"actions": [{"action": "forward", "description": "앞으로 이동"}]}
    decision, _ = await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert decision.action.type == "forward"
    assert decision.proposed_actions[0].action == "forward"
    assert memories.rows[-1]["raw_action"]["action"] == "forward"
    assert stages.rows[-1]["model_response"]["actions"][0]["action"] == "forward"


@pytest.mark.asyncio
async def test_malformed_json_keeps_actual_usage_and_repairs_once():
    brain, obs, retrieve, provider, _, _, _, calls, _ = setup()
    original = provider.complete
    first = True

    async def malformed(messages, *args):
        nonlocal first
        if first:
            first = False
            return 'not JSON', {"provider": "gpu", "model": "persona-qwen", "input_tokens": 11, "output_tokens": 4}
        return await original(messages, *args)

    provider.complete = malformed
    await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert len(calls) == brain.fast.budget.requests == 4
    assert calls[0]["error"] == "model_output_error"
    assert calls[0]["input_tokens"] == 11 and calls[0]["output_tokens"] == 4
    assert brain.fast.budget.tokens == 45


@pytest.mark.asyncio
async def test_u_type_enter_submits_once_in_the_actual_executor():
    from uxagent.actions import ActionExecutor
    from uxagent.browser import BrowserSession
    from uxagent.observation import observe
    from uxagent.schemas import UAction

    async with BrowserSession(False, 900, 700) as browser:
        await browser.active.set_content('''<form onsubmit="event.preventDefault();
            document.querySelector('#result').textContent=document.querySelector('input').value">
            <input aria-label="검색"><button>제출</button></form><p id="result">대기</p>''')
        obs, registry = await observe(browser)
        target = obs.input_elements[0].id
        action, _ = FastLoop.adapt_action(UAction(action="type", target=target, text="러닝화",
                                                  enter=True, description="러닝화 검색"), obs)
        executor = ActionExecutor(browser, [], settle_ms=50)
        executor.publish(registry)
        result = await executor.execute(action)
        assert result.ok, result.error
        assert await browser.active.locator('#result').inner_text() == "러닝화"


@pytest.mark.asyncio
async def test_gpu_runner_uses_u_flow_for_two_turns_with_fake_http(tmp_path, monkeypatch):
    from uxagent.runner import run_study

    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / 'configs/study.json').read_text(encoding='utf-8'))
    config.update(persona_file=str(root / 'configs/persona.json'), max_steps=2, enable_wonder=False)
    study = tmp_path / 'study.json'
    study.write_text(json.dumps(config), encoding='utf-8')
    monkeypatch.setenv('PERSONA_QWEN_API_URL', 'http://127.0.0.1:8001/v1/chat/completions')
    requests = []

    class Response:
        def __init__(self, content):
            self.content = content

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps({'model': 'persona-qwen', 'choices': [{'message': {'content': self.content}}],
                               'usage': {'prompt_tokens': 7, 'completion_tokens': 3}}).encode()

    def urlopen(request, timeout):
        payload = json.loads(request.data)
        requests.append(payload)
        system = payload['messages'][0]['content']
        if system.startswith('FAST_STAGE:'):
            stage = system.split(':', 1)[1].splitlines()[0]
            if stage == 'decision':
                decision_payload = json.loads(payload['messages'][-1]['content'])
                content = {'actions': [{'action': 'click',
                    'target': decision_payload['valid_targets']['clickable'][1], 'description': '검색'}]}
            else:
                content = {'perception': {'observations': ['검색 화면']},
                           'feedback': {'thoughts': ['직전 검색 제안을 확인']},
                           'plan': {'plan': '검색 확인', 'rationale': '검색 버튼 확인', 'next_step': '검색'}}[stage]
        elif system.startswith('SLOW_STAGE:importance'):
            content = {'score': 5, 'rationale': '기억 확인'}
        elif system.startswith('SLOW_STAGE:wonder'):
            content = {'thoughts': []}
        else:
            content = {'insights': []}
        return Response(json.dumps(content))

    monkeypatch.setattr('uxagent.llm.urllib.request.urlopen', urlopen)
    folder, summary = await run_study(study, 'gpu', None, False, tmp_path / 'runs')
    assert summary['termination_reason'] == 'max_steps', summary.get('last_error')
    assert summary['action_attempts'] == 2
    assert summary['provider'] == 'gpu' and summary['model'] == 'persona-qwen'
    assert summary['brain']['fast']['feedback']['completed'] == 1
    calls = [json.loads(line) for line in (folder / 'llm_calls.jsonl').read_text(encoding='utf-8').splitlines()]
    assert summary['llm_request_count'] == len(calls) >= len(requests)
    fast_calls = [call for call in calls if call.get("module") == "fast"]
    assert fast_calls and all(call["schema_version"] == "2.0" for call in fast_calls)
    assert all("request" in call and "response" in call and "method_name" in call
               and "recorded_at" in call for call in fast_calls)
    assert all("retrieve_result" in call for call in fast_calls)
    assert all(request['model'] == 'persona-qwen' for request in requests)
    steps = [json.loads(line) for line in (folder / 'steps.jsonl').read_text(encoding='utf-8').splitlines()]
    assert all(step['decision']['proposed_actions'][0]['action'] == 'click' for step in steps)
    assert all(step['result']['ok'] for step in steps)
