import pytest

from uxagent.memory import MemoryStore


def test_fast_plan_and_slow_reflection_choose_different_memories():
    now = [0.0]
    store = MemoryStore("run-search", clock=lambda: now[0])
    old_plan = store.append("plan", "검색 계획", importance=10)
    now[0] = 120.0
    recent_observation = store.append("observation", "무관한 화면", importance=1)

    baseline = [item["memory_id"] for item in store.retrieve("계획", limit=2, now_ms=120000)]
    fast = [item["memory_id"] for item in store.retrieve("계획", limit=2, now_ms=120000,
                                                           mode="fast_plan")]
    slow = [item["memory_id"] for item in store.retrieve("계획", limit=2, now_ms=120000,
                                                           mode="slow")]

    assert baseline == [old_plan.memory_id, recent_observation.memory_id]
    assert fast[0] == old_plan.memory_id
    assert slow[0] == recent_observation.memory_id


def test_unscored_memory_is_searchable_and_updated_score_changes_rank():
    now = [0.0]
    store = MemoryStore("run-search", clock=lambda: now[0])
    scored = store.append("observation", "무관한 기록", importance=8)
    pending = store.append("observation", "가방 검색")
    before = store.retrieve("가방 검색", limit=2, now_ms=0, mode="fast")
    assert before[0]["memory_id"] == pending.memory_id
    assert 0 <= before[0]["retrieval_score"] <= 1

    store.update_importance(pending.memory_id, 1, "stage-1")
    after = store.retrieve("가방 검색", limit=2, now_ms=0, mode="fast")
    assert after[0]["memory_id"] == pending.memory_id
    assert after[0]["retrieval_score"] != before[0]["retrieval_score"]
    assert scored.memory_id in {row["memory_id"] for row in after}


def test_unknown_search_mode_is_rejected():
    store = MemoryStore("run-search")
    store.append("observation", "기억")
    with pytest.raises(ValueError, match="search mode"):
        store.retrieve("기억", mode="unknown")


def test_fast_decision_prefers_action_history_to_past_observation():
    store = MemoryStore("run-search")
    old_observation = store.append("observation", "검색 버튼", importance=10)
    action = store.append("action", "검색 버튼 클릭", importance=1)

    baseline = store.retrieve("검색 버튼", limit=2, now_ms=0)
    decision = store.retrieve("검색 버튼", limit=2, now_ms=0, mode="fast_decision")

    assert baseline[0]["memory_id"] == old_observation.memory_id
    assert decision[0]["memory_id"] == action.memory_id
    assert decision[1]["retrieval_score"] == 0


def test_recency_has_sixty_second_half_life_and_ties_choose_newest():
    now = [0.0]
    store = MemoryStore("run-search", clock=lambda: now[0])
    old = store.append("observation", "같은 내용", importance=5)
    now[0] = 60.0
    new = store.append("observation", "같은 내용", importance=5)
    ranked = store.retrieve("같은 내용", limit=2, now_ms=60000, mode="slow")

    assert ranked[0]["memory_id"] == new.memory_id
    assert ranked[1]["memory_id"] == old.memory_id
    assert ranked[0]["retrieval_score"] - ranked[1]["retrieval_score"] == pytest.approx(0.3)
