import asyncio

import pytest

from uxagent.llm import BudgetManager
from uxagent.memory import MemoryStore
from uxagent.schemas import Persona
from uxagent.slow_loop import SlowLoop


class Writer:
    def __init__(self):
        self.records = []

    def write(self, value):
        self.records.append(value)


def test_unscored_memory_is_retrievable_and_score_update_keeps_original_record():
    originals, changes = Writer(), Writer()
    store = MemoryStore("r", originals, change_writer=changes)
    entry = store.append("observation", "검은 가방 찾기", source_observation_ids=["obs-1"])
    before = (entry.memory_id, entry.seq, entry.created_at, entry.created_monotonic_ms)

    assert entry.importance is None
    assert store.retrieve("가방", 1)[0]["memory_id"] == entry.memory_id
    assert store.update_importance(entry.memory_id, 9, "stage-importance-1") is True
    assert entry.importance == 9
    assert (entry.memory_id, entry.seq, entry.created_at, entry.created_monotonic_ms) == before
    assert originals.records[0]["importance"] is None
    assert changes.records[0]["change"] == "importance_scored"
    assert changes.records[0]["importance_after"] == 9
    assert changes.records[0]["source_stage_record_id"] == "stage-importance-1"
    with pytest.raises(ValueError):
        store.update_importance(entry.memory_id, 11, "stage-bad")


@pytest.mark.asyncio
async def test_slow_scores_pending_memories_with_shared_budget_and_stage_provenance():
    class Provider:
        def __init__(self):
            self.messages = []

        async def complete(self, messages, model, temperature, max_tokens):
            self.messages.append(messages)
            if "Rate the importance of one memory" in messages[0]["content"]:
                return '{"score":8,"rationale":"Needed for the task"}', {
                    "model": model, "input_tokens": 12, "output_tokens": 4}
            return '{"insights":[]}', {"model": model, "input_tokens": 10, "output_tokens": 2}

    original, changes, stages, tasks, calls = Writer(), Writer(), Writer(), Writer(), Writer()
    store = MemoryStore("r", original, change_writer=changes)
    entry = store.append("observation", "검색 입력이 보인다", source_observation_ids=["obs-1"])
    persona = Persona.model_validate({"persona_id": "p1", "background": "초보 쇼핑 사용자",
        "digital_familiarity": "낮음", "preferences": ["간단한 검색"], "constraints": {}, "intent": "가방 찾기"})
    provider, budget = Provider(), BudgetManager(None, None)
    slow = SlowLoop(provider, budget, "mock-v1", 0.2, 100, store, tasks, stages, calls.write,
                    importance_enabled=True)

    slow.schedule_reflection(persona, "가방 찾기", "obs-1")
    await slow.worker

    assert entry.importance == 8
    assert budget.requests == len(provider.messages) == 2
    importance = next(row for row in stages.records if row["stage"] == "importance")
    assert importance["source_memory_ids"] == [entry.memory_id]
    assert changes.records[0]["source_stage_record_id"] == importance["record_id"]
    assert any(row["kind"] == "importance" and row["status"] == "completed" for row in tasks.records)
    assert any(row["stage"] == "importance" for row in calls.records)


@pytest.mark.asyncio
async def test_late_importance_for_evicted_memory_does_not_recreate_it():
    gate, started = asyncio.Event(), asyncio.Event()

    class Provider:
        async def complete(self, messages, model, temperature, max_tokens):
            if "Rate the importance of one memory" in messages[0]["content"]:
                started.set()
                await gate.wait()
                return '{"score":10,"rationale":"Useful"}', {"model": model, "input_tokens": 2, "output_tokens": 2}
            return '{"insights":[]}', {"model": model, "input_tokens": 2, "output_tokens": 2}

    changes, stages, tasks = Writer(), Writer(), Writer()
    store = MemoryStore("r", change_writer=changes, max_active_memories=10)
    first = store.append("observation", "첫 기억")
    persona = Persona.model_validate({"persona_id": "p1", "background": "사용자",
        "digital_familiarity": "보통", "preferences": ["간단한 검색"], "constraints": {}, "intent": "찾기"})
    slow = SlowLoop(Provider(), BudgetManager(None, None), "mock-v1", 0.2, 100,
                    store, tasks, stages, importance_enabled=True)
    slow.schedule_reflection(persona, "찾기", "obs-1")
    await started.wait()
    for index in range(10):
        store.append("action", f"추가 {index}")
    assert first.memory_id not in {row.memory_id for row in store.entries}
    gate.set()
    await slow.worker

    assert first.memory_id not in {row.memory_id for row in store.entries}
    assert not any(row.get("change") == "importance_scored" and row["memory_id"] == first.memory_id
                   for row in changes.records)
    assert any(row["kind"] == "importance" and row["status"] == "discarded" for row in tasks.records)


@pytest.mark.asyncio
@pytest.mark.parametrize("response,expected_status", [
    ('{"score":11,"rationale":"Invalid"}', "failed"),
    ('{"score":7,"rationale":"Useful"}', "skipped"),
])
async def test_importance_failure_or_budget_keeps_memory_unscored(response, expected_status):
    class Provider:
        async def complete(self, messages, model, temperature, max_tokens):
            if "Rate the importance of one memory" in messages[0]["content"]:
                return response, {"model": model, "input_tokens": 2, "output_tokens": 2}
            return '{"insights":[]}', {"model": model, "input_tokens": 2, "output_tokens": 2}

    tasks, changes = Writer(), Writer()
    store = MemoryStore("r", change_writer=changes)
    entry = store.append("observation", "검색 화면")
    persona = Persona.model_validate({"persona_id": "p1", "background": "사용자",
        "digital_familiarity": "보통", "preferences": ["간단한 검색"], "constraints": {}, "intent": "검색"})
    budget = BudgetManager(0 if expected_status == "skipped" else None, None)
    slow = SlowLoop(Provider(), budget, "mock-v1", 0.2, 100, store, tasks, Writer(),
                    importance_enabled=True)
    slow.schedule_reflection(persona, "검색", "obs-1")
    await slow.worker

    assert entry.importance is None
    assert not any(row["change"] == "importance_scored" for row in changes.records)
    assert any(row["kind"] == "importance" and row["status"] == expected_status
               for row in tasks.records)
