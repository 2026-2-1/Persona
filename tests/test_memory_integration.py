import json
from pathlib import Path

import pytest

from uxagent.llm import MockProvider
from uxagent.runner import run_study
from uxagent.memory import MemoryStore


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.asyncio
@pytest.mark.parametrize("capacity", [10, 64])
async def test_memory_logs_trace_scores_evictions_and_slow_sources_in_one_run(
        tmp_path, monkeypatch, capacity):
    original_complete = MockProvider.complete
    plan_inputs = []

    async def capture(self, messages, *args, **kwargs):
        if "FAST_STAGE:plan" in messages[0]["content"]:
            plan_inputs.append(json.loads(messages[-1]["content"]))
        return await original_complete(self, messages, *args, **kwargs)

    monkeypatch.setattr(MockProvider, "complete", capture)
    config = json.loads((ROOT / "configs/study.json").read_text(encoding="utf-8"))
    config["persona_file"] = str(ROOT / "configs/persona.json")
    config["max_active_memories"] = capacity
    config["enable_wonder"] = False
    study = tmp_path / "study.json"
    study.write_text(json.dumps(config), encoding="utf-8")

    run_dir, summary = await run_study(study, "mock", None, False, tmp_path / "runs")
    originals = read_jsonl(run_dir / "memory.jsonl")
    changes = read_jsonl(run_dir / "memory_changes.jsonl")
    tasks = read_jsonl(run_dir / "brain_tasks.jsonl")
    stages = read_jsonl(run_dir / "brain_stages.jsonl")
    calls = read_jsonl(run_dir / "llm_calls.jsonl")
    original_ids = {row["memory_id"] for row in originals}
    evicted_ids = {row["memory_id"] for row in changes if row["change"] == "evicted"}
    scored_ids = {row["memory_id"] for row in changes if row["change"] == "importance_scored"}

    assert summary["termination_reason"] in ("agent_finished", "max_steps")
    assert summary["metrics"]["recording"]["rate"] == 1
    assert originals and all(row["importance"] is None for row in originals)
    assert len(original_ids) == len(originals)
    assert len(original_ids - evicted_ids) <= capacity
    assert scored_ids
    assert all(row["memory_id"] in original_ids for row in changes)
    assert all(row["memory_id"] in original_ids and 1 <= row["importance_after"] <= 10
               for row in changes if row["change"] == "importance_scored")
    assert all(set(row["source_memory_ids"]).issubset(original_ids) for row in tasks)
    assert all(set(row["source_memory_ids"]).issubset(original_ids) for row in stages)
    assert any(row["kind"] == "reflection" and row["status"] == "completed"
               for row in tasks)
    assert sum(row["stage"] == "importance" for row in calls) == len(scored_ids)
    assert summary["budget"]["requests"] == len(calls)
    assert plan_inputs and all(isinstance(m, str) for payload in plan_inputs for m in payload["memories"])
    assert [payload["current_timestamp"] for payload in plan_inputs] == list(range(len(plan_inputs)))
    # No embedding configured: U supplies only the recent prefix. Capacity ten
    # can evict earlier actions; do not require ranked duplicates from word search.
    assert any("kind: action;" in m for payload in plan_inputs for m in payload["memories"])
    assert all("recent_actions" not in payload and "old_plan" in payload for payload in plan_inputs)
    assert any(row["kind"] == "thought" for row in originals)
    assert all(row["content_status"] == "generated" and row["raw_action"] for row in originals if row["kind"] == "action")
    assert not any("API_KEY" in json.dumps(row) for row in [*originals, *changes, *tasks, *stages])


def test_empty_and_full_capacity_search_preserves_monotonic_ids_and_old_high_score():
    store = MemoryStore("run", max_active_memories=10)
    assert store.retrieve("가방") == []
    old_high = store.append("plan", "가방 검색 계획", importance=10)
    for index in range(10):
        store.append("action", f"최근 행동 {index}", importance=1)

    assert len(store.entries) == 10
    assert old_high.memory_id in {entry.memory_id for entry in store.entries}
    assert store.entries[-1].seq == 11
    assert store.append("observation", "추가 관찰", importance=5).seq == 12
    assert len(store.entries) == 10
