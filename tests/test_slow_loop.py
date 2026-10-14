import asyncio
import json

import pytest

from uxagent.runner import run_study
from uxagent.llm import BudgetManager
from uxagent.memory import MemoryStore
from uxagent.schemas import Persona
from uxagent.slow_loop import SlowLoop


class RecordingWriter:
    def __init__(self):
        self.records = []

    def write(self, value):
        self.records.append(value)


class SlowProvider:
    model = "fake-slow-v1"

    def __init__(self, gate=None, fail=False):
        self.gate = gate
        self.fail = fail
        self.calls = []

    async def complete(self, messages, model, temperature, max_tokens):
        self.calls.append((messages, model))
        if self.gate:
            await self.gate.wait()
        if self.fail:
            if isinstance(self.fail, BaseException):
                raise self.fail
            raise RuntimeError("provider failed")
        system = messages[0]["content"]
        if "Review whether the supplied plan" in system:
            result = {"review": "계획이 의도와 일치합니다.", "suggested_revisions": []}
        else:
            payload = json.loads(messages[-1]["content"])
            ids = [entry["memory_id"] for entry in payload["memories"]]
            result = {"insights": [{"summary": "조건을 다시 확인합니다.", "source_memory_ids": ids[:1]}]}
        return json.dumps(result, ensure_ascii=False), {
            "model": "provider-actual-v2", "input_tokens": 12, "output_tokens": 5,
        }


@pytest.mark.asyncio
async def test_reflection_and_plan_review_queue_without_limit_and_keep_plan_immutable():
    tasks, stages = RecordingWriter(), RecordingWriter()
    store = MemoryStore("run-1")
    source = store.append("observation", "상품 검색 화면", source_observation_ids=["obs-1"])
    plan_memory = store.append("plan", "상품을 검색하고 조건을 확인", source_observation_ids=["obs-1"])
    provider = SlowProvider()
    calls = []
    persona = Persona.model_validate({"persona_id": "p1", "background": "사용자", "digital_familiarity": "보통",
                                      "preferences": ["검은색"], "constraints": {}, "intent": "검은 가방 검색"})
    slow = SlowLoop(provider, BudgetManager(10, 10000), "configured-model", 0.2, 1000,
                    store, tasks, stages, calls.append)

    reflection_id = slow.schedule_reflection(persona, "검은 가방 검색", "obs-1")
    review_id = slow.schedule_plan_review(persona, "검은 가방 검색", "상품을 검색하고 조건을 확인",
                                          "obs-1", "plan-1", 1)
    assert reflection_id and review_id
    assert reflection_id != review_id
    await slow.worker

    assert [event["status"] for event in tasks.records] == [
        "scheduled", "scheduled", "started", "completed", "started", "completed",
    ]
    assert [event["kind"] for event in tasks.records if event["status"] == "scheduled"] == [
        "reflection", "plan_review",
    ]
    review = next(record for record in stages.records if record["stage"] == "plan_review")
    assert review["observation_id"] == "obs-1"
    assert review["plan_id"] == "plan-1" and review["plan_version"] == 1
    review_task_id = next(event["task_id"] for event in tasks.records
                          if event["status"] == "scheduled" and event["kind"] == "plan_review")
    assert any(call["task_id"] == review_task_id and call["model"] == "provider-actual-v2"
               for call in calls)
    assert next(entry for entry in store.entries if entry.memory_id == plan_memory.memory_id).text == "상품을 검색하고 조건을 확인"
    assert source.importance == 5
    assert all(entry.importance == 5 for entry in store.entries)


@pytest.mark.asyncio
async def test_slow_tasks_do_not_block_caller_and_record_failure():
    tasks = RecordingWriter()
    gate = asyncio.Event()
    store = MemoryStore("run-2")
    store.append("observation", "초기 화면", source_observation_ids=["obs-2"])
    persona = Persona.model_validate({"persona_id": "p1", "background": "사용자", "digital_familiarity": "보통",
                                      "preferences": ["검색"], "constraints": {}, "intent": "검색"})
    slow = SlowLoop(SlowProvider(gate=gate, fail=True), BudgetManager(10, 10000), "fake", 0.2,
                    1000, store, tasks, RecordingWriter())

    task_id = slow.schedule_reflection(persona, "검색", "obs-2")
    assert task_id
    assert slow.worker is not None
    await asyncio.sleep(0)
    assert slow.status == "running"
    gate.set()
    await slow.worker

    failed = next(event for event in tasks.records if event["status"] == "failed")
    assert failed["task_id"] == task_id
    assert failed["reason_code"] == "reflection_call_failed"


@pytest.mark.asyncio
async def test_slow_snapshot_keeps_score_and_memory_values_when_live_entry_changes():
    tasks, stages = RecordingWriter(), RecordingWriter()
    gate = asyncio.Event()
    store = MemoryStore("run-3")
    original = store.append("observation", "초기 화면", source_observation_ids=["obs-3"])
    provider = SlowProvider(gate=gate)
    persona = Persona.model_validate({"persona_id": "p1", "background": "사용자", "digital_familiarity": "보통",
                                      "preferences": ["검색"], "constraints": {}, "intent": "검색"})
    slow = SlowLoop(provider, BudgetManager(10, 10000), "fake", 0.2, 1000,
                    store, tasks, stages)
    slow.schedule_reflection(persona, "검색", "obs-3")
    while not provider.calls:
        await asyncio.sleep(0)

    store.entries[0] = original.model_copy(update={"text": "나중에 바뀐 화면", "importance": 9})
    gate.set()
    await slow.worker

    prompt_memory = json.loads(provider.calls[0][0][-1]["content"])["memories"][0]
    assert prompt_memory["text"] == "초기 화면"
    assert prompt_memory["importance"] == 5


@pytest.mark.asyncio
async def test_plan_review_timeout_is_recorded_as_failure():
    tasks = RecordingWriter()
    store = MemoryStore("run-timeout")
    store.append("plan", "상품을 검색한다", source_observation_ids=["obs-timeout"])
    persona = Persona.model_validate({"persona_id": "p1", "background": "사용자", "digital_familiarity": "보통",
                                      "preferences": ["검색"], "constraints": {}, "intent": "검색"})
    slow = SlowLoop(SlowProvider(fail=TimeoutError("timed out")), BudgetManager(10, 10000),
                    "fake", 0.2, 1000, store, tasks, RecordingWriter())

    slow.schedule_plan_review(persona, "검색", "상품을 검색한다", "obs-timeout", "plan-timeout", 1)
    await slow.worker

    failed = next(event for event in tasks.records if event["status"] == "failed")
    assert failed["reason_code"] == "plan_review_timeout"


@pytest.mark.asyncio
async def test_runner_schedules_reflection_after_perception_and_review_after_plan(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configs/study.json").read_text(encoding="utf-8"))
    config["persona_file"] = str(root / "configs/persona.json")
    # Legacy opt-in remains false here: #43 makes Slow mandatory for AI runs.
    config["enable_slow_loop"] = False
    config["max_steps"] = 1
    study_path = tmp_path / "study.json"
    study_path.write_text(json.dumps(config), encoding="utf-8")

    run_dir, summary = await run_study(study_path, "mock", None, False, tmp_path / "runs")

    events = [json.loads(line) for line in (run_dir / "brain_tasks.jsonl").read_text().splitlines()]
    scheduled = [event for event in events
                 if event["status"] == "scheduled" and event["kind"] in {"reflection", "plan_review"}]
    assert [event["kind"] for event in scheduled] == ["reflection", "plan_review"]
    assert all(any(event["task_id"] == task["task_id"] and
                   event["status"] in {"completed", "cancelled", "failed", "skipped"}
                   for event in events) for task in scheduled)
    assert summary["brain"]["slow"]["events"]["scheduled"] == 2
    assert summary["brain_status"] in {"completed", "incomplete"}
    assert all(summary["brain"]["fast"][stage]["completed"] == 1
               for stage in ("perception", "plan", "decision"))
    fast_stage_records = [json.loads(line) for line in (run_dir / "brain_stages.jsonl").read_text().splitlines()
                          if json.loads(line)["stage"] in {"perception", "plan", "decision"}]
    assert all(record["task_id"] and any(event["task_id"] == record["task_id"] and
               event["status"] == "completed" and event["output_record_ids"] == [record["record_id"]]
               for event in events) for record in fast_stage_records)
    assert summary["importance_scoring_status"] == "fixed_equal_5"
