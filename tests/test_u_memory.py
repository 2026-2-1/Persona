import math

import pytest

from uxagent.memory import MemoryStore


def ready(store, entry, vector):
    store.embedding_cache[entry.memory_id] = vector


def test_u_dot_product_step_recency_and_importance_sum():
    store = MemoryStore('u')
    old = store.append('reflection', 'unrelated words', importance=10)
    store.timestamp = 5
    new = store.append('action', 'query', importance=1)
    ready(store, old, [3., 0.]); ready(store, new, [.1, 0.])
    rows = store.retrieve_u('query', query_vector=[2., 0.], mode='fast_decision')
    scores = {row['memory_id']: row['retrieval_score'] for row in rows}
    assert scores[old.memory_id] == pytest.approx(6 + math.exp(-5) + 1)
    assert scores[new.memory_id] == pytest.approx((.2 + 1 + .1) * 10)
    assert rows[0]['memory_id'] == new.memory_id
    plan = store.retrieve_u('query', query_vector=[2., 0.], mode='fast_plan')
    assert next(row['retrieval_score'] for row in plan if row['memory_id'] == old.memory_id) == pytest.approx(scores[old.memory_id] * 10)


def test_u_recent_windows_and_ranked_duplicates_without_source_step_dedup():
    store = MemoryStore('u'); store.timestamp = 4
    excluded = store.append('observation', 'too old', [1], importance=5)
    store.timestamp = 5
    observation = store.append('observation', 'boundary', [1], importance=5)
    store.timestamp = 3
    action = store.append('action', 'boundary', [1], importance=5)
    store.timestamp = 8
    for entry in store.entries: ready(store, entry, [1.])
    rows = store.retrieve_u('q', query_vector=[1.], mode='fast_plan')
    ids = [row['memory_id'] for row in rows]
    assert ids[:2] == [observation.memory_id, action.memory_id]
    assert ids.count(observation.memory_id) == ids.count(action.memory_id) == 2
    assert ids.count(excluded.memory_id) == 1


def test_u_no_embeddings_returns_recent_only_no_word_fallback():
    store = MemoryStore('u')
    observation = store.append('observation', 'q')
    store.append('reflection', 'q')
    assert store.retrieve_u('q', mode='fast_decision') == []
    assert [r['memory_id'] for r in store.retrieve_u('q', mode='fast_plan')] == [observation.memory_id]


def test_u_default_top20_and_missing_vectors_use_only_ready_ids():
    store = MemoryStore('u')
    for i in range(30):
        entry = store.append('reflection', str(i), importance=1)
        ready(store, entry, [float(i)])
    store.append('reflection', 'pending', importance=10)
    rows = store.retrieve_u('q', query_vector=[1.], mode='fast_decision')
    assert len(rows) == 20
    assert [r['text'] for r in rows] == [str(i) for i in range(29, 9, -1)]


@pytest.mark.parametrize('vector', [[], [1., 2.], [float('nan')], [True]])
def test_u_rejects_invalid_or_incompatible_query_vectors(vector):
    store = MemoryStore('u'); entry = store.append('reflection', 'x', importance=5)
    ready(store, entry, [1.])
    with pytest.raises(ValueError, match='embedding'):
        store.retrieve_u('q', query_vector=vector, mode='fast_decision')


@pytest.mark.asyncio
async def test_u_query_embedding_only_when_memory_vectors_ready_and_usage_preserved():
    from uxagent.llm import BudgetManager
    class Provider:
        def __init__(self): self.calls = []
        async def embed(self, texts, model):
            self.calls.append((texts, model))
            return [[2.]], {'provider':'separate', 'model':model, 'input_tokens':3}
    provider = Provider(); store = MemoryStore('u'); budget = BudgetManager(None, None); logs = []
    entry = store.append('reflection', 'memory', importance=5)
    assert await store.retrieve_u_with_embeddings('q', provider, budget, 'embed', logs.append, mode='fast_decision') == []
    assert not provider.calls
    ready(store, entry, [1.])
    rows = await store.retrieve_u_with_embeddings('q', provider, budget, 'embed', logs.append, mode='fast_decision')
    assert provider.calls == [(['q'], 'embed')]
    assert rows[0]['retrieval_score'] == pytest.approx(3.5)
    assert budget.requests == 1 and budget.tokens == 3 and budget.reserved_tokens == 0
    assert logs[0]['provider'] == 'separate' and logs[0]['input_tokens'] == 3


@pytest.mark.asyncio
async def test_u_invalid_query_response_records_actual_usage_without_word_fallback():
    from uxagent.llm import BudgetManager
    class Provider:
        async def embed(self, texts, model): return [[1., 2.]], {'input_tokens':7}
    store = MemoryStore('u'); entry = store.append('reflection', 'q', importance=5)
    ready(store, entry, [1.]); budget = BudgetManager(None, None); logs = []
    with pytest.raises(ValueError, match='embedding'):
        await store.retrieve_u_with_embeddings('q', Provider(), budget, 'embed', logs.append, mode='fast_decision')
    assert budget.tokens == 7 and budget.reserved_tokens == 0
    assert len(logs) == 1 and logs[0]['input_tokens'] == 7 and logs[0]['error'] == 'ValueError'


@pytest.mark.asyncio
async def test_u_query_cancel_settles_budget_and_keeps_run_caches_separate():
    import asyncio
    from uxagent.llm import BudgetManager
    started = asyncio.Event(); stopped = asyncio.Event()
    class Provider:
        async def embed(self, texts, model):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
    store = MemoryStore('one'); other = MemoryStore('two')
    entry = store.append('reflection', 'q', importance=5)
    ready(store, entry, [1.]); budget = BudgetManager(None, None); logs = []
    job = asyncio.create_task(store.retrieve_u_with_embeddings('q', Provider(), budget, 'embed', logs.append))
    await started.wait(); job.cancel()
    with pytest.raises(asyncio.CancelledError): await job
    assert stopped.is_set() and budget.requests == 1 and budget.reserved_tokens == 0
    assert len(logs) == 1 and logs[0]['input_tokens'] is None and logs[0]['error'] == 'CancelledError'
    assert other.embedding_cache == {} and store.embedding_cache == {entry.memory_id:[1.]}


def test_u_eviction_uses_importance_then_oldest_without_kind_or_stage_protection():
    store = MemoryStore('u', max_active_memories=10)
    high_wonder = store.append('wonder', 'high', importance=10)
    low = store.append('observation', 'low', importance=1)
    store.set_current_stage_memories([low.memory_id])
    store.set_slow_snapshot_memories([low.memory_id])
    for i in range(9): store.append('action', str(i), importance=5)
    ids = {entry.memory_id for entry in store.entries}
    assert low.memory_id not in ids and high_wonder.memory_id in ids
    assert len(ids) == 10 and store.last_seq == 11


def test_u_eviction_importance_ties_remove_oldest_and_preserve_raw_records():
    class Writer:
        def __init__(self): self.rows=[]
        def write(self, row): self.rows.append(row)
    original, changes = Writer(), Writer()
    store = MemoryStore('u', original, max_active_memories=10, change_writer=changes)
    old = store.append('observation', 'old', importance=5)
    ready(store, old, [1.])
    store.set_current_stage_memories([old.memory_id])
    for i in range(10): store.append('thought', str(i), importance=5)
    assert old.memory_id not in {entry.memory_id for entry in store.entries}
    assert old.memory_id not in store.embedding_cache
    assert original.rows[0]['memory_id'] == old.memory_id and len(original.rows) == 11
    assert changes.rows[0]['reason_code'] == 'active_capacity_importance_then_oldest'


def test_unscored_new_memory_survives_full_scored_store_until_its_score_arrives():
    store = MemoryStore('u')
    for i in range(64): store.append('reflection',str(i),importance=10)
    cursor=store.last_seq
    pending=store.append('observation','new unscored')
    assert len(store.entries)==64
    assert store.since(cursor)[0].memory_id==pending.memory_id and pending.importance is None
    store.update_importance(pending.memory_id,1,'importance-stage')
    next_pending=store.append('thought','next unscored')
    active={entry.memory_id for entry in store.entries}
    assert pending.memory_id not in active and next_pending.memory_id in active
