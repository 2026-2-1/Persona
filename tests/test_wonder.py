import asyncio
import json

import pytest

from uxagent.brain import Brain
from uxagent.llm import BudgetManager
from uxagent.memory import MemoryStore
from uxagent.runner import run_study
from uxagent.schemas import Persona
from uxagent.slow_loop import SlowLoop


class Writer:
    def __init__(self):
        self.records = []

    def write(self, value):
        self.records.append(value)


class Provider:
    def __init__(self, wonder_gate=None, thought="저녁에는 산책을 해 볼까?"):
        self.calls = []
        self.wonder_gate = wonder_gate
        self.thought = thought

    async def complete(self, messages, model, temperature, max_tokens):
        system = messages[0]["content"]
        payload = json.loads(messages[-1]["content"])
        self.calls.append((system, payload))
        if "WONDER_PERSONA_ONLY" in system:
            if self.wonder_gate:
                await self.wonder_gate.wait()
            result = {"thought": self.thought}
        elif "Review whether the supplied plan" in system:
            result = {"review": "계획 점검", "suggested_revisions": []}
        else:
            result = {"insights": []}
        return json.dumps(result, ensure_ascii=False), {
            "model": "fake", "input_tokens": 12, "output_tokens": 5,
        }


def persona():
    return Persona(persona_id="p1", background="산책을 즐기는 사람",
                   digital_familiarity="보통", preferences=["차"],
                   constraints={"budget": 30000}, intent="검은 가방 구매")


def slow_loop(*, seed=139, budget=None, provider=None, memory=None, defer_adoption=True):
    tasks, stages, draws, calls = Writer(), Writer(), Writer(), Writer()
    store = memory or MemoryStore("run-wonder")
    slow = SlowLoop(provider or Provider(), budget or BudgetManager(None, None),
                    "fake", 0.2, 100, store, tasks, stages, calls.write,
                    defer_adoption=defer_adoption, wonder_enabled=True,
                    wonder_seed=seed, wonder_draw_writer=draws)
    return slow, store, tasks, stages, draws, calls


@pytest.mark.asyncio
async def test_started_slow_tasks_draw_once_and_wonder_uses_only_persona():
    slow, store, tasks, stages, draws, calls = slow_loop()
    first = slow.schedule_reflection(persona(), "비밀 과업 문장", "obs-secret")
    second = slow.schedule_plan_review(persona(), "비밀 과업 문장", "비밀 계획",
                                       "obs-secret", "plan-secret", 1)
    await slow.worker
    await asyncio.gather(*slow.wonder_tasks)

    assert [row["parent_task_id"] for row in draws.records] == [first, second]
    assert [row["selected"] for row in draws.records] == [True, False]
    assert all(row["seed"] == 139 for row in draws.records)
    wonder_calls = [payload for system, payload in slow.provider.calls
                    if "WONDER_PERSONA_ONLY" in system]
    assert len(wonder_calls) == 1
    assert set(wonder_calls[0]) == {"persona"}
    assert set(wonder_calls[0]["persona"]) == {
        "persona_id", "background", "digital_familiarity", "preferences", "constraints",
    }
    assert "비밀 과업 문장" not in json.dumps(wonder_calls[0], ensure_ascii=False)
    assert "obs-secret" not in json.dumps(wonder_calls[0], ensure_ascii=False)
    assert any(row["kind"] == "wonder" and row["status"] == "completed" for row in tasks.records)
    wonder_stage = next(row for row in stages.records if row["stage"] == "wonder")
    assert wonder_stage["task_id"] == draws.records[0]["wonder_task_id"]
    assert wonder_stage["observation_id"] is None
    assert wonder_stage["source_memory_ids"] == []
    assert wonder_stage["text"].startswith("가정된 생각:")


@pytest.mark.asyncio
async def test_nonwinning_draw_makes_no_wonder_request():
    slow, store, tasks, stages, draws, calls = slow_loop(seed=0)
    slow.schedule_reflection(persona(), "가방 찾기", "obs-1")
    await slow.worker

    assert len(draws.records) == 1 and draws.records[0]["selected"] is False
    assert not any(row["kind"] == "wonder" for row in tasks.records)
    assert not any("WONDER_PERSONA_ONLY" in system for system, _ in slow.provider.calls)


@pytest.mark.asyncio
async def test_general_condition_wonder_uses_only_shared_constraints():
    slow, store, tasks, stages, draws, calls = slow_loop()
    brain = Brain(None, slow, store, persona(), persona_mode="general")
    brain.schedule_reflection("가방 찾기", "obs-1")
    await slow.worker
    await asyncio.gather(*slow.wonder_tasks)

    payload = next(payload for system, payload in slow.provider.calls
                   if "WONDER_PERSONA_ONLY" in system)
    assert payload == {"persona": {"constraints": {"budget": 30000}}}


@pytest.mark.asyncio
async def test_wonder_adoption_keeps_generated_provenance():
    slow, store, tasks, stages, draws, calls = slow_loop()
    brain = Brain(None, slow, store, persona())
    slow.schedule_reflection(persona(), "가방 찾기", "obs-1")
    await slow.worker
    await asyncio.gather(*slow.wonder_tasks)
    brain.begin_stage("perception", "obs-2")

    wonder = next(entry for entry in store.entries if entry.kind == "wonder")
    assert wonder.content_status == "generated"
    assert wonder.source_observation_ids == []
    assert wonder.source_stage_record_id == next(row["record_id"] for row in stages.records
                                                 if row["stage"] == "wonder")
    assert any(row["kind"] == "wonder" and row["status"] == "adopted" for row in tasks.records)


@pytest.mark.asyncio
async def test_completed_wonder_is_published_with_other_shared_memory_outputs():
    slow, store, tasks, stages, draws, calls = slow_loop()
    brain = Brain(None, slow, store, persona())
    slow.schedule_reflection(persona(), "가방 찾기", "obs-1")
    await slow.worker
    await asyncio.gather(*slow.wonder_tasks)

    boundary = brain.begin_stage("perception", "obs-2")

    assert any(entry["kind"] == "wonder" for entry in boundary)
    assert any(entry.kind == "wonder" for entry in store.entries)


@pytest.mark.asyncio
async def test_wonder_budget_exhaustion_is_recorded_without_generated_memory():
    slow, store, tasks, stages, draws, calls = slow_loop(budget=BudgetManager(1, None))
    slow.schedule_reflection(persona(), "가방 찾기", "obs-1")
    await slow.worker
    await asyncio.gather(*slow.wonder_tasks)

    assert draws.records[0]["selected"] is True
    assert any(row["kind"] == "wonder" and row["status"] == "skipped"
               and row["reason_code"] == "budget_exceeded" for row in tasks.records)
    assert not any(row["stage"] == "wonder" for row in stages.records)
    assert not any(entry.kind == "wonder" for entry in store.entries)


@pytest.mark.asyncio
async def test_wonder_does_not_evict_task_memory_at_capacity():
    store = MemoryStore("run-wonder", max_active_memories=10)
    original = [store.append("observation", f"필수 작업 근거 {i}") for i in range(10)]
    slow, _, tasks, stages, draws, calls = slow_loop(memory=store)
    brain = Brain(None, slow, store, persona())
    slow.schedule_reflection(persona(), "가방 찾기", "obs-1")
    await slow.worker
    await asyncio.gather(*slow.wonder_tasks)
    brain.begin_stage("perception", "obs-2")

    assert {entry.memory_id for entry in store.entries} == {entry.memory_id for entry in original}
    # The shared store evicts the newly appended Wonder at capacity; the Brain
    # does not gate its publication or evict any of the original task memories.
    assert any(row["kind"] == "wonder" and row["status"] == "adopted" for row in tasks.records)
    assert any(row["stage"] == "wonder" for row in stages.records)


def test_task_memory_eviction_prefers_wonder_even_when_wonder_is_recent():
    store = MemoryStore("run-wonder", max_active_memories=10)
    task_entries = [store.append("observation", f"과업 근거 {i}") for i in range(9)]
    wonder = store.append("wonder", "가정된 생각: 차를 마실까?", content_status="generated")

    store.append("action", "새 과업 행동")

    assert wonder.memory_id not in {entry.memory_id for entry in store.entries}
    assert all(entry.memory_id in {current.memory_id for current in store.entries}
               for entry in task_entries)


@pytest.mark.asyncio
async def test_inflight_wonder_cancels_without_changing_observation():
    gate = asyncio.Event()
    slow, store, tasks, stages, draws, calls = slow_loop(provider=Provider(wonder_gate=gate))
    brain = Brain(None, slow, store, persona())
    brain.begin_stage("perception", "obs-current")
    slow.schedule_reflection(persona(), "가방 찾기", "obs-current")
    await slow.worker
    assert slow.worker.done()
    assert brain.begin_stage("perception", "obs-current") == []
    for _ in range(20):
        if any(row["kind"] == "wonder" and row["status"] == "started" for row in tasks.records):
            break
        await asyncio.sleep(0)
    await brain.close()

    assert brain.current_observation_id == "obs-current"
    assert any(row["kind"] == "wonder" and row["status"] == "cancelled" for row in tasks.records)
    assert not any(row["stage"] == "wonder" for row in stages.records)


@pytest.mark.asyncio
async def test_wonder_rejects_secret_output():
    slow, store, tasks, stages, draws, calls = slow_loop(provider=Provider(thought="api_key: secret-test-value"))
    slow.schedule_reflection(persona(), "가방 찾기", "obs-1")
    await slow.worker
    await asyncio.gather(*slow.wonder_tasks)

    assert any(row["kind"] == "wonder" and row["status"] == "failed" for row in tasks.records)
    assert "secret-test-value" not in json.dumps(stages.records, ensure_ascii=False)
    assert "secret-test-value" not in json.dumps(calls.records, ensure_ascii=False)


@pytest.mark.asyncio
async def test_provider_internal_retry_does_not_repeat_the_task_draw():
    class RetryingProvider(Provider):
        def __init__(self):
            super().__init__()
            self.network_attempts = 0

        async def complete(self, messages, model, temperature, max_tokens):
            if "Summarize up to three brief insights" in messages[0]["content"]:
                self.network_attempts += 2  # provider retries one transport failure internally
            return await super().complete(messages, model, temperature, max_tokens)

    provider = RetryingProvider()
    slow, store, tasks, stages, draws, calls = slow_loop(provider=provider)
    slow.schedule_reflection(persona(), "가방 찾기", "obs-1")
    await slow.worker
    await asyncio.gather(*slow.wonder_tasks)

    assert provider.network_attempts == 2
    assert len(draws.records) == 1


@pytest.mark.asyncio
async def test_u_runner_uses_every_cycle_wonder_without_legacy_seed_or_draws(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configs/study.json").read_text(encoding="utf-8"))
    config.update(persona_file=str(root / "configs/persona.json"), max_steps=1,
                  wonder_seed=139, enable_wonder=False)
    study = tmp_path / "study.json"
    study.write_text(json.dumps(config), encoding="utf-8")

    run_dir, summary = await run_study(study, "mock", None, False, tmp_path / "runs")

    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    tasks = [json.loads(line) for line in (run_dir / "brain_tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    started = [row['kind'] for row in tasks if row['status'] == 'started'
               and row['kind'] in {'reflection', 'wonder', 'memory_update', 'plan_review'}]
    assert not (run_dir / 'wonder_draws.jsonl').exists()
    assert 'wonder_seed' not in run and 'wonder_seed' not in summary['brain']['slow']
    assert run['wonder_policy'] == 'u_every_cycle'
    assert started[:3] == ['reflection', 'wonder', 'memory_update']
    assert all(kind == ['reflection', 'wonder', 'memory_update'][index % 3]
               for index, kind in enumerate(started))
    memories = [json.loads(line) for line in (run_dir / 'memory.jsonl').read_text(encoding='utf-8').splitlines()]
    assert any(row['kind'] == 'thought' for row in memories)
    assert not any(row['kind'] == 'wonder' for row in memories)
    assert summary['brain']['slow']['worker_starts'] == 1


def test_detail_and_report_label_wonder_as_generated_assumption(tmp_path):
    from pathlib import Path
    from uxagent.monitor import Dashboard
    from uxagent.reports import export_report

    root = Path(__file__).resolve().parents[1]
    run_dir = tmp_path / "runs" / "wonder-run"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text('{"run_id":"wonder-run"}', encoding="utf-8")
    (run_dir / "config.json").write_text('{"task":"찾기"}', encoding="utf-8")
    (run_dir / "persona.json").write_text('{}', encoding="utf-8")
    (run_dir / "summary.json").write_text('{"run_id":"wonder-run","verification":"unknown"}', encoding="utf-8")
    (run_dir / "brain_stages.jsonl").write_text(json.dumps({
        "record_id": "stage-wonder-1", "stage": "wonder",
        "run_id": "wonder-run",
        "text": "가정된 생각: 오늘은 차를 마셔 볼까?",
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "memory.jsonl").write_text(json.dumps({
        "memory_id": "m-wonder-1", "kind": "wonder", "source_stage_record_id": "stage-wonder-1",
        "run_id": "wonder-run",
        "content_status": "generated",
    }) + "\n", encoding="utf-8")
    dashboard = Dashboard(tmp_path / "runs", tmp_path / "personas", root / "configs/study.json")

    detail = dashboard.run_detail("wonder-run")
    assert detail["wonder"]["thoughts"][0]["stored"] is True
    assert "실제 사용자" in export_report(detail, "md")
    assert "가정된 생각" in export_report(detail, "md")
