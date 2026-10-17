import asyncio
import json

import pytest

from uxagent import slow_loop as module
from uxagent.brain import Brain
from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager
from uxagent.memory import MemoryStore
from uxagent.schemas import Observation, Persona, ElementInfo


class Writer:
    def __init__(self):
        self.rows = []

    def write(self, row):
        self.rows.append(row)


class Provider:
    model = "persona-qwen"

    def __init__(self):
        self.calls = []
        self.hook = None
        self.reflections = 0
        self.third_reflection = asyncio.Event()

    async def complete(self, messages, model, temperature, max_tokens):
        stage = messages[0]['content'].split('SLOW_STAGE:', 1)[1].splitlines()[0]
        payload = json.loads(messages[1]['content'])
        self.calls.append((stage, payload, model))
        if self.hook:
            result = await self.hook(stage, payload)
            if result is not None:
                return json.dumps(result), {'provider': 'gpu', 'model': model, 'input_tokens': 4, 'output_tokens': 2}
        if stage == 'reflection':
            self.reflections += 1
            if self.reflections == 3:
                self.third_reflection.set()
                await asyncio.Event().wait()
            result = {'insights': [f'성찰 {self.reflections}']}
        elif stage == 'wonder':
            result = {'thoughts': ['맥락을 참고한 생각']}
        else:
            result = {'score': 8, 'rationale': '중요도'}
        return json.dumps(result), {'provider': 'gpu', 'model': model, 'input_tokens': 4, 'output_tokens': 2}


def make_slow(provider=None, *, capacity=64, budget=None, embedding_model=None, run_id='run-slow'):
    provider = provider or Provider()
    memory_writer, changes, tasks, stages, calls = Writer(), Writer(), Writer(), Writer(), Writer()
    store = MemoryStore(run_id, memory_writer, max_active_memories=capacity, change_writer=changes)
    cls = getattr(module, 'ContinuousSlowLoop')
    slow = cls(provider, budget or BudgetManager(None, None), 'persona-qwen', .2, 1200,
               store, tasks, stages, calls.write, embedding_model=embedding_model)
    return slow, store, provider, tasks, stages, calls, changes


@pytest.mark.asyncio
async def test_single_worker_repeats_reflect_wonder_update_and_publishes_directly():
    slow, store, provider, tasks, stages, calls, _ = make_slow()
    store.append('observation', '검색 결과')
    first = slow.start({'background': '사용자'}, '러닝화 찾기', 'obs-first', plan_getter=lambda: '현재 계획')
    assert slow.start({'background': '무시해야 할 중복 시작'}, '다른 과업') is first
    try:
        await asyncio.wait_for(provider.third_reflection.wait(), timeout=2)
        assert slow.summary()['cycles'] == 2
        assert slow.summary()['worker_starts'] == 1
        started = [r['kind'] for r in tasks.rows if r['status'] == 'started' and r['kind'] != 'importance']
        assert started[:6] == ['reflection', 'wonder', 'memory_update'] * 2
        assert not {'plan_review', 'adopted', 'discarded'} & {r['kind'] for r in tasks.rows}
        assert not any(r['status'] in {'adopted', 'discarded'} for r in tasks.rows)
        assert [m.kind for m in store.entries].count('thought') == 2
        assert [m.kind for m in store.entries].count('reflection') == 2
        wonder = next(payload for stage, payload, _ in provider.calls if stage == 'wonder')
        assert set(wonder) == {'persona', 'memories', 'intent'}
        assert wonder['intent'] == '러닝화 찾기'
        assert any('검색 결과' in item for item in wonder['memories'])
        importance = next(payload for stage, payload, _ in provider.calls if stage == 'importance')
        assert importance['plan'] == '현재 계획' and isinstance(importance['memory'], str)
        assert any(m.kind == 'thought' for m in store.entries if m.importance == 8)
        assert any('성찰 1' in row['text'] for row in store.retrieve('성찰', 64, deduplicate_steps=False))
        assert all(row['provider'] == 'gpu' for row in calls.rows)
        assert stages.rows
    finally:
        await slow.close()
    assert slow.worker.done() and slow.summary()['active'] == 0
    assert slow.budget.reserved_tokens == 0


@pytest.mark.asyncio
async def test_reflection_cursor_survives_a_full_64_entry_array():
    provider = Provider()
    first_started, release_first = asyncio.Event(), asyncio.Event()

    async def hook(stage, payload):
        if stage == 'reflection' and not first_started.is_set():
            first_started.set()
            await release_first.wait()

    provider.hook = hook
    slow, store, *_ = make_slow(provider)
    for index in range(64):
        store.append('observation', f'원래 기억 {index}')
    slow.start({}, '과업')
    try:
        await asyncio.wait_for(first_started.wait(), timeout=2)
        for index in range(12):
            store.append('action', f'새 기억 {index}')
        assert len(store.entries) == 64
        release_first.set()
        await asyncio.wait_for(provider.third_reflection.wait(), timeout=2)
        payloads = [payload for stage, payload, _ in provider.calls if stage == 'reflection']
        assert len(payloads[0]['memories']) == 64
        assert any('새 기억 11' in text for text in payloads[1]['memories'])
        assert not any('원래 기억' in text for text in payloads[1]['memories'])
        assert slow.reflection_cursor > 64
        assert len(store.entries) <= 64
    finally:
        await slow.close()


@pytest.mark.asyncio
async def test_empty_thoughts_and_empty_new_memories_are_valid():
    provider = Provider()
    second_reflect = asyncio.Event()
    reflect_count = 0

    async def hook(stage, payload):
        nonlocal reflect_count
        if stage == 'reflection':
            reflect_count += 1
            assert payload['memories'] == []
            if reflect_count == 2:
                second_reflect.set()
                await asyncio.Event().wait()
            return {'insights': []}
        if stage == 'wonder':
            assert payload['memories'] == []
            return {'thoughts': []}

    provider.hook = hook
    slow, store, _, _, stages, *_ = make_slow(provider)
    slow.start({}, '과업')
    try:
        await asyncio.wait_for(second_reflect.wait(), timeout=2)
        assert slow.summary()['cycles'] == 1 and store.entries == []
        assert any(row['stage'] == 'wonder' for row in stages.rows)
    finally:
        await slow.close()


@pytest.mark.asyncio
async def test_memory_update_runs_embedding_and_importance_together_and_discards_late_ids():
    provider = Provider()
    embedding_started, scoring_started, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    second_reflect = asyncio.Event()
    reflects = 0

    async def hook(stage, payload):
        nonlocal reflects
        if stage == 'reflection':
            reflects += 1
            if reflects == 2:
                second_reflect.set()
                await asyncio.Event().wait()
            return {'insights': []}
        if stage == 'wonder':
            return {'thoughts': []}
        scoring_started.set()
        await embedding_started.wait()
        await release.wait()
        return {'score': 10, 'rationale': '늦은 점수'}

    async def embed(texts, model):
        embedding_started.set()
        await scoring_started.wait()
        await release.wait()
        return [[1.0, 2.0] for _ in texts], {'model': model, 'input_tokens': 3, 'output_tokens': 0}

    provider.hook, provider.embed = hook, embed
    slow, store, _, tasks, _, calls, changes = make_slow(provider, capacity=10, embedding_model='fake-embedding')
    first = store.append('observation', '처음 기억')
    slow.start({}, '과업')
    try:
        await asyncio.wait_for(asyncio.gather(embedding_started.wait(), scoring_started.wait()), timeout=2)
        for index in range(10):
            store.append('action', f'새 기억 {index}')
        release.set()
        await asyncio.wait_for(second_reflect.wait(), timeout=2)
        assert first.memory_id not in store.embedding_cache
        assert all(entry.importance is None for entry in store.entries)
        assert not any(row['change'] == 'importance_scored' for row in changes.rows)
        assert any(row.get('reason_code') == 'source_memory_evicted' for row in tasks.rows)
        assert any(row['module'] == 'embedding' for row in calls.rows)
    finally:
        await slow.close()
    assert slow.budget.reserved_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['json', 'budget'])
async def test_failure_and_budget_stop_the_worker_without_claiming_completion(failure):
    provider = Provider()
    if failure == 'json':
        async def invalid(*args):
            return 'not json', {'provider': 'gpu', 'model': 'persona-qwen', 'input_tokens': 5, 'output_tokens': 2}
        provider.complete = invalid
    budget = BudgetManager(0 if failure == 'budget' else None, None)
    slow, store, _, tasks, _, calls, _ = make_slow(provider, budget=budget)
    slow.start({}, '과업')
    await asyncio.wait_for(slow.worker, timeout=2)
    assert slow.summary()['cycles'] == 0
    assert slow.status == ('failed' if failure == 'json' else 'budget_exceeded')
    assert any(row['status'] == ('failed' if failure == 'json' else 'skipped') for row in tasks.rows)
    assert store.entries == [] and budget.reserved_tokens == 0
    if failure == 'json':
        assert calls.rows[0]['input_tokens'] == 5 and calls.rows[0]['error'] == 'model_output_error'
    else:
        assert budget.requests == 0 and calls.rows == []
    await slow.close()


@pytest.mark.asyncio
async def test_fast_can_make_two_decisions_while_reflection_is_blocked():
    provider = Provider()
    started = asyncio.Event()

    async def both(messages, model, temperature, max_tokens):
        system = messages[0]['content']
        if 'SLOW_STAGE:' in system:
            started.set()
            await asyncio.Event().wait()
        stage = system.split('FAST_STAGE:', 1)[1].splitlines()[0]
        if stage == 'plan':
            await started.wait()
        result = {'perception': {'observations': ['검색 화면']}, 'feedback': {'thoughts': []},
                  'plan': {'plan': '검색', 'rationale': '조건 확인', 'next_step': '검색'},
                  'decision': {'actions': [{'action': 'click', 'target': 'search', 'description': '검색'}]}}[stage]
        return json.dumps(result), {'model': model, 'input_tokens': 1, 'output_tokens': 1}

    provider.complete = both
    slow, store, *_ = make_slow(provider)
    persona = Persona(persona_id='p', background='PRIVATE_BACKGROUND', digital_familiarity='PRIVATE_SKILL',
                      preferences=['PRIVATE_PREF'], constraints={}, intent='검색')
    fast = FastLoop(provider, slow.budget, 'persona-qwen', .2, 1200)
    brain = Brain(fast, slow, store, persona, persona_mode='general')
    observation = Observation(observation_id='obs-1', tab_id='tab-1', url='https://shop.test', title='Shop',
                              html='검색', clickable_elements=[ElementInfo(id='search', role='button', name='검색')])

    async def retrieve(query, mode):
        return list(store.retrieve(query, 64, mode=mode, deduplicate_steps=False))

    try:
        first, _ = await asyncio.wait_for(brain.forward('검색', observation, 1, retrieve), timeout=2)
        second, _ = await asyncio.wait_for(brain.forward('검색', observation, 2, retrieve), timeout=2)
        assert first.action.target_id == second.action.target_id == 'search'
        assert not slow.worker.done()
    finally:
        await brain.close()
    assert slow.worker.done() and slow.budget.reserved_tokens == 0


@pytest.mark.asyncio
async def test_wonder_uses_last_50_and_publishes_thoughts_without_a_draw():
    slow, store, provider, tasks, *_ = make_slow()
    for index in range(64):
        store.append('observation', f'구별 가능한 기억 {index}')
    slow.start({'background': '사람'}, '공유 과업')
    try:
        await asyncio.wait_for(provider.third_reflection.wait(), timeout=2)
        payload = next(payload for stage, payload, _ in provider.calls if stage == 'wonder')
        assert len(payload['memories']) == 50
        assert any('구별 가능한 기억 63' in text for text in payload['memories'])
        assert not any('content: 구별 가능한 기억 0' in text for text in payload['memories'])
        assert not any(entry.kind == 'wonder' for entry in store.entries)
        assert any(entry.kind == 'thought' for entry in store.entries)
        assert not any(row['kind'] == 'plan_review' for row in tasks.rows)
        assert 'wonder_seed' not in slow.summary()
    finally:
        await slow.close()


@pytest.mark.asyncio
async def test_cancellation_during_joint_update_joins_embedding_and_score_requests():
    provider = Provider()
    embed_started, score_started = asyncio.Event(), asyncio.Event()
    stopped = set()

    async def hook(stage, payload):
        if stage == 'reflection':
            return {'insights': []}
        if stage == 'wonder':
            return {'thoughts': []}
        score_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.add('score')

    async def embed(texts, model):
        embed_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.add('embedding')

    provider.hook, provider.embed = hook, embed
    slow, store, _, tasks, _, calls, _ = make_slow(provider, embedding_model='test-embedding')
    store.append('observation', '기억')
    slow.start({}, '과업')
    try:
        await asyncio.wait_for(asyncio.gather(embed_started.wait(), score_started.wait()), timeout=2)
    finally:
        await slow.close()
    assert stopped == {'score', 'embedding'}
    assert slow.worker.done() and slow.summary()['active'] == 0
    assert slow.budget.reserved_tokens == 0
    assert {row['kind'] for row in tasks.rows if row['status'] == 'cancelled'} == {'importance', 'embedding', 'memory_update'}
    assert len(calls.rows) == slow.budget.requests
    assert not store.embedding_cache and store.entries[0].importance is None


@pytest.mark.asyncio
async def test_run_scopes_and_personas_do_not_leak_into_other_loops():
    first = make_slow(run_id='run-first')
    second = make_slow(run_id='run-second')
    first[1].append('observation', 'FIRST_MEMORY')
    second[1].append('observation', 'SECOND_MEMORY')
    first[0].start({'background': 'FIRST_PERSONA'}, 'FIRST_INTENT')
    second[0].start({'constraints': {}, 'intent': 'SECOND_INTENT'}, 'SECOND_INTENT')
    try:
        await asyncio.wait_for(asyncio.gather(first[2].third_reflection.wait(), second[2].third_reflection.wait()), timeout=2)
        assert 'SECOND_' not in json.dumps(first[2].calls)
        assert 'FIRST_' not in json.dumps(second[2].calls)
        assert all(row['run_id'] == 'run-first' for row in first[3].rows)
        assert all(row['run_id'] == 'run-second' for row in second[3].rows)
    finally:
        await asyncio.gather(first[0].close(), second[0].close())
    assert first[0].summary()['active'] == second[0].summary()['active'] == 0


@pytest.mark.asyncio
async def test_close_before_the_worker_starts_does_not_leave_scheduled_state():
    slow, _, _, tasks, _, calls, _ = make_slow()
    slow.start({}, '과업')
    await slow.close()
    assert slow.worker.cancelled()
    assert slow.status == 'cancelled' and slow.summary()['active'] == 0
    assert calls.rows == tasks.rows == []
    with pytest.raises(RuntimeError, match='closed'):
        slow.start({}, '다른 실행')
