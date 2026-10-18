import asyncio
import json
from pathlib import Path

import pytest

import uxagent.runner as runner_module
from uxagent.fast_loop import FastLoop
from uxagent.llm import MockProvider
from uxagent.actions import ActionExecutor
from uxagent.runner import run_study


ROOT = Path(__file__).resolve().parents[1]


def study_file(tmp_path, **overrides):
    config = json.loads((ROOT / "configs/study.json").read_text(encoding="utf-8"))
    config.update(persona_file=str(ROOT / "configs/persona.json"), **overrides)
    path = tmp_path / "study.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def read_steps(run_dir):
    return [json.loads(line) for line in (run_dir / "steps.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.mark.asyncio
async def test_intermediate_success_does_not_end_exploration_and_final_eval_follows_terminate(monkeypatch, tmp_path):
    events = []

    class ContinueThenTerminateProvider(MockProvider):
        async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
            system = messages[0]["content"]
            if system.startswith("FAST_STAGE:decision"):
                events.append("decision")
                if events.count("decision") == 1:
                    return json.dumps({"actions": [{"action": "refresh", "description": "최신 화면을 다시 봅니다."}]}), {
                        "model": "mock-v1", "input_tokens": 1, "output_tokens": 1,
                    }
                return json.dumps({"actions": [{"action": "terminate", "description": "탐색을 마칩니다."}]}), {
                    "model": "mock-v1", "input_tokens": 1, "output_tokens": 1,
                }
            return await super().complete(messages, model, temperature, max_tokens)

    async def success_evaluator(page, evaluator_id, checks=None, **kwargs):
        events.append("evaluate")
        return {"verification": "success", "reason": "configured_checks", "feature_checks": []}

    original_close = runner_module.Brain.close

    async def record_close(self):
        events.append("slow_closed")
        await original_close(self)

    monkeypatch.setattr(runner_module, "MockProvider", ContinueThenTerminateProvider)
    monkeypatch.setattr(runner_module, "evaluate", success_evaluator)
    monkeypatch.setattr(runner_module.Brain, "close", record_close)
    run_dir, summary = await run_study(study_file(tmp_path, max_steps=4), "mock", None,
                                       False, tmp_path / "runs")
    steps = read_steps(run_dir)
    final = json.loads((run_dir / "final_evaluation.json").read_text(encoding="utf-8"))

    assert events.count("decision") == 2
    assert summary["termination_reason"] == "agent_finished"
    assert summary["verification"] == "success"
    assert events.index("slow_closed") < events.index("evaluate")
    assert events.count("evaluate") == 1
    assert len(steps) == 2 and steps[0]["action"] and steps[0]["result"]
    assert all(step["evaluation"]["verification"] == "unknown" for step in steps)
    assert steps[-1]["decision"]["finish"]["claim"] == "completed"
    assert final["termination_reason"] == "agent_finished"
    assert final["termination_step_id"] == summary["final_evaluation_step_id"] == 2
    assert final["evaluation"]["verification"] == "success"
    assert final["observation_id"] == summary["final_observation_id"]
    assert summary["last_observation_id"] == final["observation_id"]
    assert (run_dir / "observations" / f'{final["observation_id"]}.json').is_file()
    assert (run_dir / "observations" / f'{final["observation_id"]}.png').is_file()


@pytest.mark.asyncio
async def test_finish_claim_keeps_current_evaluation_separate(monkeypatch, tmp_path):
    events = []
    original_evaluate = runner_module.evaluate

    class FinishProvider(MockProvider):
        async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
            system = messages[0]["content"]
            if system.startswith("FAST_STAGE:"):
                stage = system.split(":", 1)[1].splitlines()[0]
                events.append(stage)
                if stage == "decision":
                    return json.dumps({"actions": [{"action": "terminate", "description": "완료 선언"}]}), {
                        "model": "mock-v1", "input_tokens": 1, "output_tokens": 1,
                    }
            return await super().complete(messages, model, temperature, max_tokens)

    async def record_evaluation(page, evaluator_id, checks=None):
        events.append("evaluate")
        return await original_evaluate(page, evaluator_id, checks)

    monkeypatch.setattr(runner_module, "MockProvider", FinishProvider)
    monkeypatch.setattr(runner_module, "evaluate", record_evaluation)
    run_dir, summary = await run_study(study_file(tmp_path), "mock", None,
                                       False, tmp_path / "runs")
    step = read_steps(run_dir)[0]
    final = json.loads((run_dir / "final_evaluation.json").read_text(encoding="utf-8"))

    assert events.index("evaluate") > events.index("decision")
    assert events.count("evaluate") == 1
    assert summary["termination_reason"] == "agent_finished"
    assert summary["verification"] == "failure"
    assert step["decision"]["finish"]["claim"] == "completed"
    assert step["action"] is None and step["result"] is None
    assert step["evaluation"]["verification"] == "unknown"
    assert final["evaluation"]["verification"] == "failure"
    assert step["pre_observed_at"]


@pytest.mark.asyncio
async def test_final_capture_failure_is_unknown_and_does_not_reuse_a_stale_observation(monkeypatch, tmp_path):
    original_observe = runner_module.observe
    calls = 0
    evaluator_calls = []

    class FinishProvider(MockProvider):
        async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
            if messages[0]["content"].startswith("FAST_STAGE:decision"):
                return json.dumps({"actions": [{"action": "terminate", "description": "종료"}]}), {
                    "model": "mock-v1", "input_tokens": 1, "output_tokens": 1,
                }
            return await super().complete(messages, model, temperature, max_tokens)

    async def fail_final_observation(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("final capture failed")
        return await original_observe(*args, **kwargs)

    async def should_not_evaluate(*args, **kwargs):
        evaluator_calls.append(True)
        raise AssertionError("stale observation must not be evaluated")

    monkeypatch.setattr(runner_module, "MockProvider", FinishProvider)
    monkeypatch.setattr(runner_module, "observe", fail_final_observation)
    monkeypatch.setattr(runner_module, "evaluate", should_not_evaluate)
    run_dir, summary = await run_study(study_file(tmp_path), "mock", None,
                                       False, tmp_path / "runs")
    final = json.loads((run_dir / "final_evaluation.json").read_text(encoding="utf-8"))

    assert summary["termination_reason"] == "agent_finished"
    assert summary["verification"] == "unknown"
    assert summary["last_error"]["code"] == "final_observation_error"
    assert final["observation_id"] is None
    assert final["previous_observation_id"] == summary["last_observation_id"]
    assert final["evaluation"]["reason"] == "final_observation_error"
    assert evaluator_calls == []


@pytest.mark.asyncio
async def test_final_evaluator_exception_is_unknown_without_changing_termination(monkeypatch, tmp_path):
    class FinishProvider(MockProvider):
        async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
            if messages[0]["content"].startswith("FAST_STAGE:decision"):
                return json.dumps({"actions": [{"action": "terminate", "description": "종료"}]}), {
                    "model": "mock-v1", "input_tokens": 1, "output_tokens": 1,
                }
            return await super().complete(messages, model, temperature, max_tokens)

    async def fail_evaluation(*args, **kwargs):
        raise RuntimeError("private evaluator detail")

    monkeypatch.setattr(runner_module, "MockProvider", FinishProvider)
    monkeypatch.setattr(runner_module, "evaluate", fail_evaluation)
    run_dir, summary = await run_study(study_file(tmp_path), "mock", None,
                                       False, tmp_path / "runs")
    final = json.loads((run_dir / "final_evaluation.json").read_text(encoding="utf-8"))

    assert summary["termination_reason"] == "agent_finished"
    assert summary["verification"] == "unknown"
    assert summary["evaluator"]["reason"] == "evaluator_error"
    assert final["observation_id"] == summary["final_observation_id"]
    assert final["evaluation"]["reason"] == "evaluator_error"
    assert "private evaluator detail" not in json.dumps(final)


@pytest.mark.asyncio
async def test_slow_shutdown_error_skips_final_capture_and_evaluation(monkeypatch, tmp_path):
    original_close = runner_module.Brain.close
    evaluator_calls = []

    class FinishProvider(MockProvider):
        async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
            if messages[0]["content"].startswith("FAST_STAGE:decision"):
                return json.dumps({"actions": [{"action": "terminate", "description": "종료"}]}), {
                    "model": "mock-v1", "input_tokens": 1, "output_tokens": 1,
                }
            return await super().complete(messages, model, temperature, max_tokens)

    async def close_then_raise(self):
        await original_close(self)
        raise RuntimeError("private slow shutdown detail")

    async def should_not_evaluate(*args, **kwargs):
        evaluator_calls.append(True)
        return {"verification": "success", "reason": "unexpected", "feature_checks": []}

    monkeypatch.setattr(runner_module, "MockProvider", FinishProvider)
    monkeypatch.setattr(runner_module.Brain, "close", close_then_raise)
    monkeypatch.setattr(runner_module, "evaluate", should_not_evaluate)
    run_dir, summary = await run_study(study_file(tmp_path), "mock", None,
                                       False, tmp_path / "runs")
    final = json.loads((run_dir / "final_evaluation.json").read_text(encoding="utf-8"))

    assert summary["termination_reason"] == "agent_finished"
    assert summary["verification"] == "unknown"
    assert summary["last_error"]["code"] == "slow_shutdown_error"
    assert final["evaluation"]["reason"] == "slow_shutdown_error"
    assert evaluator_calls == []


@pytest.mark.asyncio
async def test_post_action_capture_error_is_followed_by_a_fresh_final_evaluation(monkeypatch, tmp_path):
    original_observe = runner_module.observe
    calls = 0

    async def fail_second_observation(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("capture failed")
        return await original_observe(*args, **kwargs)

    monkeypatch.setattr(runner_module, "observe", fail_second_observation)
    run_dir, summary = await run_study(study_file(tmp_path), "mock", None,
                                       False, tmp_path / "runs")
    step = read_steps(run_dir)[0]

    assert summary["termination_reason"] == "browser_error"
    assert summary["verification"] == "failure"
    assert summary["last_error"]["code"] == "post_observation_error"
    assert summary["action_attempts"] == 1
    assert step["action"] and step["result"]
    assert step["error"]["code"] == "post_observation_error"
    assert step["evaluation"]["verification"] == "unknown"
    final = json.loads((run_dir / "final_evaluation.json").read_text(encoding="utf-8"))
    assert final["evaluation"]["verification"] == "failure"
    assert (run_dir / "observations" / f'{step["observation_id"]}.json').is_file()


@pytest.mark.asyncio
async def test_executor_failure_is_separate_from_decision_and_evaluation(monkeypatch, tmp_path):
    original_execute = ActionExecutor.execute
    proposals_before_execution = []

    async def capture_proposals(self, action):
        paths = list((tmp_path / "runs").glob("*/memory.jsonl"))
        rows = [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines()]
        proposals_before_execution.extend(row for row in rows if row["kind"] == "action")
        return await original_execute(self, action)

    monkeypatch.setattr(ActionExecutor, "execute", capture_proposals)
    class MissingTargetProvider(MockProvider):
        async def complete(self, messages, model=None, temperature=0.2, max_tokens=1200):
            system = messages[0]["content"]
            if system.startswith("FAST_STAGE:decision"):
                return json.dumps({"actions": [{"action": "click", "target": "missing-target",
                                                 "description": "대상을 누릅니다."}]}), {
                    "model": "mock-v1", "input_tokens": 1, "output_tokens": 1,
                }
            return await super().complete(messages, model, temperature, max_tokens)

    monkeypatch.setattr(runner_module, "MockProvider", MissingTargetProvider)
    run_dir, summary = await run_study(study_file(tmp_path, max_steps=1), "mock", None,
                                       False, tmp_path / "runs")
    step = read_steps(run_dir)[0]

    assert summary["action_attempts"] == 1
    assert proposals_before_execution[0]["raw_action"]["target"] == "missing-target"
    assert proposals_before_execution[0]["content_status"] == "generated"
    assert step["decision"]["action"]["target_id"] == "missing-target"
    assert step["result"]["ok"] is False
    assert step["result"]["error"]["code"] == "target_not_found"
    assert step["next_observation_id"] != step["observation_id"]
    assert step["evaluation"]["verification"] == step["verification"]


@pytest.mark.asyncio
async def test_model_timeout_keeps_pre_observation_and_unknown_status(monkeypatch, tmp_path):
    async def stalled_perception(self, *args, **kwargs):
        await asyncio.sleep(2)

    monkeypatch.setattr(FastLoop, "perceive_page", stalled_perception)
    run_dir, summary = await run_study(study_file(tmp_path, run_timeout_seconds=1),
                                       "mock", None, False, tmp_path / "runs")
    step = read_steps(run_dir)[0]

    assert summary["termination_reason"] == "run_timeout"
    assert summary["verification"] == "failure"
    assert step["error"]["code"] == "run_timeout"
    assert step["action"] is None and step["result"] is None
    assert step["pre_observed_at"]
    assert (run_dir / "observations" / f'{step["observation_id"]}.png').is_file()
    final = json.loads((run_dir / "final_evaluation.json").read_text(encoding="utf-8"))
    assert final["termination_reason"] == "run_timeout"
    assert final["evaluation"]["verification"] == "failure"


@pytest.mark.asyncio
async def test_stop_during_action_keeps_result_and_post_observation(monkeypatch, tmp_path):
    stop_file = tmp_path / "stop.request"
    original_execute = ActionExecutor.execute

    async def stop_while_executing(self, action):
        stop_file.touch()
        return await original_execute(self, action)

    monkeypatch.setattr(ActionExecutor, "execute", stop_while_executing)
    run_dir, summary = await run_study(study_file(tmp_path), "mock", None,
                                       False, tmp_path / "runs", stop_file=stop_file)
    steps = read_steps(run_dir)

    assert summary["termination_reason"] == "cancelled"
    assert len(steps) == 1
    assert steps[0]["decision"]["action"]
    assert steps[0]["result"] and steps[0]["next_observation_id"]
    assert steps[0]["evaluation"]["verification"] == steps[0]["verification"]
    final = json.loads((run_dir / "final_evaluation.json").read_text(encoding="utf-8"))
    assert summary["last_observation_id"] == final["observation_id"]
    assert final["observation_id"] != steps[0]["next_observation_id"]
