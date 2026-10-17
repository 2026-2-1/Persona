import asyncio
import json
from pathlib import Path

import pytest

from uxagent.brain import Brain
from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager
from uxagent.memory import MemoryStore
from uxagent.runner import run_study
from uxagent.schemas import Persona
from uxagent.slow_loop import SlowLoop


class RecordingWriter:
    def __init__(self):
        self.records = []

    def write(self, value):
        self.records.append(value)


class BrainProvider:
    model = "brain-fake-v1"

    def __init__(self, gate=None):
        self.gate = gate
        self.calls = []

    async def complete(self, messages, model, temperature, max_tokens):
        self.calls.append(messages)
        if self.gate:
            await self.gate.wait()
        system = messages[0]["content"]
        payload = json.loads(messages[-1]["content"])
        if "Review whether the supplied plan" in system:
            result = {"review": "검토 제안입니다.", "suggested_revisions": []}
        else:
            source_ids = [entry["memory_id"] for entry in payload["memories"]]
            result = {"insights": [{"summary": "이전 조건을 확인합니다.",
                                    "source_memory_ids": source_ids[:1]}]}
        return json.dumps(result, ensure_ascii=False), {
            "model": "brain-fake-v1", "input_tokens": 10, "output_tokens": 4,
        }


def make_brain(run_id="run-brain", *, provider=None, persona_mode="persona"):
    provider = provider or BrainProvider()
    events, stages = RecordingWriter(), RecordingWriter()
    memory = MemoryStore(run_id)
    slow = SlowLoop(provider, BudgetManager(None, None), "fake", 0.2, 100,
                    memory, events, stages, defer_adoption=True)
    persona = Persona.model_validate({
        "persona_id": "p1", "background": "개인 정보는 일반 조건에 전달되면 안 됩니다.",
        "digital_familiarity": "보통", "preferences": ["검은색"], "constraints": {"budget": 30000},
        "intent": "검은 가방 찾기",
    })
    fast = FastLoop(provider, BudgetManager(None, None), "fake", 0.2, 100)
    return Brain(fast, slow, memory, persona, persona_mode), events, stages, provider


@pytest.mark.asyncio
async def test_reflection_is_adopted_only_at_a_fast_stage_boundary():
    brain, events, _, _ = make_brain()
    source = brain.memory.append("observation", "검색 결과", source_observation_ids=["obs-1"])
    brain.begin_stage("perception", "obs-1")
    brain.schedule_reflection("가방 찾기", "obs-1")
    await brain.slow.worker

    assert len(brain.memory.entries) == 1
    boundary_memories = brain.begin_stage("plan", "obs-1")

    assert len(brain.memory.entries) == 2
    generated = brain.memory.entries[-1]
    assert [entry["memory_id"] for entry in boundary_memories] == [generated.memory_id]
    assert generated.source_memory_ids == [source.memory_id]
    assert generated.source_stage_record_id
    assert any(event["status"] == "adopted" for event in events.records)


@pytest.mark.asyncio
async def test_u_runner_does_not_force_adopted_reflection_into_retrieval(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configs/study.json").read_text(encoding="utf-8"))
    config["persona_file"] = str(root / "configs/persona.json")
    config["max_steps"] = 1
    config["action_timeout_ms"] = 15000
    config["wonder_seed"] = 139
    study_path = tmp_path / "study.json"
    study_path.write_text(json.dumps(config), encoding="utf-8")

    original_plan = FastLoop.make_plan
    original_decide = FastLoop.act
    original_retrieve = MemoryStore.retrieve
    original_schedule = SlowLoop.schedule_reflection
    decision_memories = []
    reflection_workers = []

    def capture_reflection_worker(self, *args, **kwargs):
        task_id = original_schedule(self, *args, **kwargs)
        reflection_workers.append(self.worker)
        return task_id

    async def plan_after_reflection(self, *args, **kwargs):
        await reflection_workers[-1]
        return await original_plan(self, *args, **kwargs)

    async def capture_decision(self, persona, task, observation, memories, *args, **kwargs):
        decision_memories.extend(memories)
        return await original_decide(self, persona, task, observation, memories,
                                     *args, **kwargs)

    def retrieve_without_reflection(self, *args, **kwargs):
        return [entry for entry in original_retrieve(self, *args, **kwargs)
                if entry["kind"] != "reflection"]

    monkeypatch.setattr(FastLoop, "make_plan", plan_after_reflection)
    monkeypatch.setattr(FastLoop, "act", capture_decision)
    monkeypatch.setattr(MemoryStore, "retrieve", retrieve_without_reflection)
    monkeypatch.setattr(SlowLoop, "schedule_reflection", capture_reflection_worker)

    _, summary = await run_study(study_path, "mock", None, False, tmp_path / "runs")

    assert summary["termination_reason"] == "max_steps", {
        "termination": summary["termination_reason"], "error": summary.get("last_error")}
    assert summary["brain"]["adoption"]["reflection"] >= 1
    assert not any(entry["kind"] == "reflection" for entry in decision_memories)


@pytest.mark.asyncio
async def test_completed_legacy_plan_review_enters_shared_memory():
    brain, events, _, _ = make_brain()
    brain.memory.append("plan", "현재 계획", source_observation_ids=["obs-1"])
    brain.begin_stage("perception", "obs-1")
    brain.begin_stage("plan", "obs-1")
    brain.schedule_plan_review("가방 찾기", "현재 계획", "obs-1", "plan-current", 2)
    await brain.slow.worker

    review_memories = brain.begin_stage("decision", "obs-1", plan_id="plan-current",
                                        plan_version=2)

    assert len(review_memories) == 1
    assert review_memories[0]["text"] == "검토 제안입니다."
    assert review_memories[0]["source_stage_record_id"]
    assert any(event["status"] == "adopted" and event["kind"] == "plan_review"
               for event in events.records)


@pytest.mark.asyncio
async def test_old_observation_does_not_gate_completed_slow_output():
    brain, events, _, _ = make_brain()
    brain.memory.append("plan", "이전 계획", source_observation_ids=["obs-old"])
    brain.begin_stage("perception", "obs-old")
    brain.begin_stage("plan", "obs-old")
    brain.schedule_plan_review("가방 찾기", "이전 계획", "obs-old", "plan-old", 1)
    await brain.slow.worker

    received = brain.begin_stage("perception", "obs-new")
    brain.begin_stage("plan", "obs-new")
    decision_reviews = brain.begin_stage("decision", "obs-new", plan_id="plan-new",
                                         plan_version=1)

    assert decision_reviews == []
    assert received[0]["text"] == "검토 제안입니다."
    assert any(entry.text == "검토 제안입니다." for entry in brain.memory.entries)
    assert any(event["status"] == "adopted" for event in events.records)
    assert not any(event.get("reason_code") == "stale_context" for event in events.records)


@pytest.mark.asyncio
@pytest.mark.parametrize(("current_plan", "current_version"), [("plan-new", 1), ("plan-old", 2)])
async def test_plan_id_and_version_are_metadata_not_output_gates(current_plan, current_version):
    brain, events, _, _ = make_brain()
    brain.memory.append("plan", "검토 대상 계획", source_observation_ids=["obs-1"])
    brain.begin_stage("perception", "obs-1")
    brain.begin_stage("plan", "obs-1")
    brain.schedule_plan_review("가방 찾기", "검토 대상 계획", "obs-1", "plan-old", 1)
    await brain.slow.worker

    reviews = brain.begin_stage("decision", "obs-1", plan_id=current_plan,
                                plan_version=current_version)

    assert reviews[0]["text"] == "검토 제안입니다."
    assert any(event["status"] == "adopted" for event in events.records)
    assert not any(event.get("reason_code") == "stale_context" for event in events.records)


@pytest.mark.asyncio
async def test_close_cancels_running_and_queued_tasks_and_general_slow_context_is_isolated():
    gate = asyncio.Event()
    provider = BrainProvider(gate)
    brain, events, _, _ = make_brain(provider=provider, persona_mode="general")
    brain.memory.append("observation", "관찰", source_observation_ids=["obs-1"])
    brain.begin_stage("perception", "obs-1")
    brain.schedule_reflection("가방 찾기", "obs-1")
    brain.schedule_reflection("가방 찾기", "obs-1")
    while not provider.calls:
        await asyncio.sleep(0)

    payload = json.loads(provider.calls[0][-1]["content"])
    assert payload["persona"] == {"constraints": {"budget": 30000}, "intent": "검은 가방 찾기"}
    await brain.close()

    cancelled = [event for event in events.records if event["status"] == "cancelled"]
    assert len(cancelled) == 2
    assert all(event["reason_code"] == "run_finished" for event in cancelled)
    assert brain.summary()["status"] == "incomplete"


@pytest.mark.asyncio
async def test_two_run_scopes_do_not_share_memories_or_slow_results():
    first, _, _, first_provider = make_brain("run-first")
    second, _, _, second_provider = make_brain("run-second")
    first_source = first.memory.append("observation", "첫 실행 전용", source_observation_ids=["obs-first"])
    second.memory.append("observation", "두 번째 실행 전용", source_observation_ids=["obs-second"])
    first.begin_stage("perception", "obs-first")
    second.begin_stage("perception", "obs-second")
    first.schedule_reflection("검색", "obs-first")
    second.schedule_reflection("검색", "obs-second")
    await asyncio.gather(first.slow.worker, second.slow.worker)

    first.begin_stage("plan", "obs-first")
    second.begin_stage("plan", "obs-second")

    first_payload = json.loads(first_provider.calls[0][-1]["content"])
    second_payload = json.loads(second_provider.calls[0][-1]["content"])
    assert [entry["text"] for entry in first_payload["memories"]] == ["첫 실행 전용"]
    assert [entry["text"] for entry in second_payload["memories"]] == ["두 번째 실행 전용"]
    assert first_source.run_id != second.memory.run_id
    assert all(entry.run_id == "run-first" for entry in first.memory.entries)
    assert all(entry.run_id == "run-second" for entry in second.memory.entries)
