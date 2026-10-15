import asyncio
import json

import pytest

from uxagent.llm import BudgetManager
from uxagent.memory import MemoryStore
from uxagent.schemas import Persona
from uxagent.slow_loop import SlowLoop


class Writer:
    def __init__(self):
        self.records = []

    def write(self, record):
        self.records.append(record)


def test_current_stage_memory_survives_recent_ten_at_capacity_ten():
    changes = Writer()
    store = MemoryStore("run", max_active_memories=10, change_writer=changes)
    current = store.append("observation", "현재 화면")
    store.set_current_stage_memories([current.memory_id])
    for index in range(10):
        store.append("action", f"후속 {index}", importance=5)

    assert len(store.entries) == 10
    assert current.memory_id in {row.memory_id for row in store.entries}
    assert any(row["reason_code"] == "recent_capacity_for_current_stage"
               for row in changes.records)


def test_pending_score_is_kept_over_old_scored_memory_if_capacity_allows():
    changes = Writer()
    store = MemoryStore("run", max_active_memories=12, change_writer=changes)
    scored = store.append("observation", "오래된 점수", importance=8)
    pending = store.append("observation", "점수 대기")
    for index in range(11):
        store.append("action", f"최근 {index}", importance=10)

    active = {row.memory_id for row in store.entries}
    assert len(active) == 12
    assert pending.memory_id in active
    assert scored.memory_id not in active
    assert changes.records[0]["memory_id"] == scored.memory_id


def test_pending_score_yields_to_recent_ten_and_removal_preserves_original():
    originals, changes = Writer(), Writer()
    store = MemoryStore("run", originals, max_active_memories=10, change_writer=changes)
    pending = store.append("observation", "점수 대기")
    for index in range(10):
        store.append("action", f"최근 {index}", importance=5)

    assert pending.memory_id not in {row.memory_id for row in store.entries}
    assert originals.records[0]["memory_id"] == pending.memory_id
    assert changes.records[0]["memory_id"] == pending.memory_id
    assert changes.records[0]["reason_code"] == "pending_importance_capacity"
    assert store.update_importance(pending.memory_id, 9, "stage-late") is False


@pytest.mark.asyncio
async def test_embedding_result_does_not_restore_evicted_memory_cache():
    gate, started = asyncio.Event(), asyncio.Event()

    class Provider:
        async def embed(self, texts, model):
            started.set()
            await gate.wait()
            return [[1.0, 0.0] for _ in texts], {"model": model, "input_tokens": len(texts)}

    store = MemoryStore("run", max_active_memories=10)
    old = store.append("observation", "오래된 기억")
    task = asyncio.create_task(store.retrieve_with_embeddings(
        "질의", 8, Provider(), BudgetManager(None, None), "mock-v1"))
    await started.wait()
    for index in range(10):
        store.append("action", f"최근 {index}", importance=5)
    gate.set()
    await task

    assert old.memory_id not in store.embedding_cache
    assert old.memory_id not in {row.memory_id for row in store.entries}


@pytest.mark.asyncio
async def test_evicted_slow_snapshot_keeps_original_source_ids():
    gate, started = asyncio.Event(), asyncio.Event()

    class Provider:
        async def complete(self, messages, model, temperature, max_tokens):
            payload = json.loads(messages[-1]["content"])
            source = payload["memories"][0]["memory_id"]
            started.set()
            await gate.wait()
            return json.dumps({"insights": [{"summary": "관찰 근거", "source_memory_ids": [source]}]}), {
                "model": model, "input_tokens": 2, "output_tokens": 2}

    originals, changes, tasks, stages = Writer(), Writer(), Writer(), Writer()
    store = MemoryStore("run", originals, max_active_memories=10, change_writer=changes)
    old = store.append("observation", "원본 화면", source_observation_ids=["obs-1"], importance=5)
    persona = Persona.model_validate({"persona_id": "p1", "background": "사용자",
        "digital_familiarity": "보통", "preferences": ["간단한 검색"],
        "constraints": {}, "intent": "검색"})
    slow = SlowLoop(Provider(), BudgetManager(None, None), "mock-v1", 0.2, 100,
                    store, tasks, stages, defer_adoption=True)
    slow.schedule_reflection(persona, "검색", "obs-1")
    await started.wait()
    for index in range(10):
        store.append("action", f"최근 {index}", importance=5)
    gate.set()
    await slow.worker

    assert old.memory_id not in {row.memory_id for row in store.entries}
    assert originals.records[0]["memory_id"] == old.memory_id
    assert changes.records[0]["reason_code"] == "slow_snapshot_capacity"
    assert any(row["kind"] == "reflection" and row["status"] == "completed" and
               old.memory_id in row["source_memory_ids"] for row in tasks.records)
    assert stages.records[0]["source_memory_ids"] == [old.memory_id]
