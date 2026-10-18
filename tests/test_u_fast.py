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


@pytest.mark.asyncio
async def test_first_turn_uses_u_payloads_and_saves_proposals_before_execution():
    brain, obs, retrieve, provider, memories, stages, _, calls, queries = setup()
    decision, sources = await brain.forward("러닝화 찾기", obs, 1, retrieve)
    assert [stage for stage, _, _ in provider.calls] == ["perception", "plan", "decision"]
    perceive = provider.calls[0][1]
    assert perceive == obs.html.replace("Crime", "***").replace("security", "***")
    plan_input, act_input = provider.calls[1][1], provider.calls[2][1]
    assert set(plan_input) == {"persona", "intent", "memories", "current_timestamp", "old_plan"}
    assert plan_input["old_plan"] == "N/A" and plan_input["current_timestamp"] == 0
    assert any("전체 페이지 관찰" in item for item in plan_input["memories"])
    assert queries == [("러닝화 찾기", "fast_plan"), ("검색어 입력", "fast_decision")]
    assert act_input["next_step"] == "검색어 입력"
    assert act_input["environment"] == obs.html
    # Reproduce U's known inputs/selects-from-clickables bug explicitly.
    assert act_input["valid_targets"]["inputs"] == act_input["valid_targets"]["clickable"]
    assert act_input["valid_targets"]["selects"] == act_input["valid_targets"]["clickable"]
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
    assert sources


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
    assert brain.fast.budget.reserved_tokens == 0


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
    assert all(request['model'] == 'persona-qwen' for request in requests)
    steps = [json.loads(line) for line in (folder / 'steps.jsonl').read_text(encoding='utf-8').splitlines()]
    assert all(step['decision']['proposed_actions'][0]['action'] == 'click' for step in steps)
    assert all(step['result']['ok'] for step in steps)
