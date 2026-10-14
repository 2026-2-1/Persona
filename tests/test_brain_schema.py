from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from uxagent.memory import MemoryStore
from uxagent.schemas import Action, BrainStageRecord, BrainTaskEvent, MemoryChangeEvent, MemoryEntry, StudyConfig


def test_brain_stage_record_keeps_generated_content_and_provenance():
    record = BrainStageRecord(
        record_id="stage-1",
        run_id="run-1",
        stage="perception",
        observation_id="obs-1",
        text="검색 입력칸이 보인다고 해석했다.",
        source_memory_ids=["m-1"],
        snapshot_seq=2,
        recorded_at=datetime(2026, 10, 14, tzinfo=timezone.utc),
    )

    restored = BrainStageRecord.model_validate_json(record.model_dump_json())
    assert restored == record
    assert restored.content_status == "generated"
    assert restored.source_memory_ids == ["m-1"]
    assert restored.observation_id == "obs-1"
    assert restored.schema_version == "1.0"


@pytest.mark.parametrize("stage", ["plan", "decision", "plan_review"])
def test_brain_stage_record_requires_plan_reference_for_plan_dependent_stages(stage):
    with pytest.raises(ValidationError):
        BrainStageRecord(
            record_id="stage-2",
            run_id="run-1",
            stage=stage,
            observation_id="obs-1",
            text="다음 행동을 고른다.",
            recorded_at=datetime(2026, 10, 14, tzinfo=timezone.utc),
        )


def test_brain_stage_record_rejects_observed_claim_and_evaluator_answer():
    base = {
        "record_id": "stage-3",
        "run_id": "run-1",
        "stage": "plan",
        "observation_id": "obs-1",
        "plan_id": "plan-1",
        "plan_version": 1,
        "text": "상품을 검색한다.",
        "recorded_at": datetime(2026, 10, 14, tzinfo=timezone.utc),
    }
    with pytest.raises(ValidationError):
        BrainStageRecord(**{**base, "content_status": "observed"})
    with pytest.raises(ValidationError):
        BrainStageRecord(**{**base, "verification": "success"})


def test_brain_stage_record_keeps_persona_only_wonder_without_observation_source():
    wonder = BrainStageRecord(
        record_id="stage-4",
        run_id="run-1",
        stage="wonder",
        text="오늘 저녁에는 무엇을 먹을까.",
        recorded_at=datetime(2026, 10, 14, tzinfo=timezone.utc),
    )
    assert wonder.observation_id is None
    assert wonder.content_status == "generated"


def test_brain_stage_record_rejects_partial_plan_reference_and_naive_time():
    base = {
        "record_id": "stage-5",
        "run_id": "run-1",
        "stage": "plan",
        "observation_id": "obs-1",
        "text": "다음 상품을 연다.",
        "recorded_at": datetime(2026, 10, 14, tzinfo=timezone.utc),
    }
    with pytest.raises(ValidationError):
        BrainStageRecord(**{**base, "plan_id": "plan-1"})
    with pytest.raises(ValidationError):
        BrainStageRecord(**{**base, "plan_id": "plan-1", "plan_version": 0})
    with pytest.raises(ValidationError):
        BrainStageRecord(**{**base, "plan_id": "plan-1", "plan_version": 1,
                            "recorded_at": datetime(2026, 10, 14)})


def test_decision_stage_keeps_action_proposal_separate_from_execution():
    action = Action(type="click", observation_id="obs-1", tab_id="tab-1", target_id="button-1")
    record = BrainStageRecord(
        record_id="stage-6", run_id="run-1", stage="decision",
        observation_id="obs-1", plan_id="plan-1", plan_version=1,
        text="버튼을 누르기로 결정했다.", action=action,
        recorded_at=datetime(2026, 10, 14, tzinfo=timezone.utc),
    )
    assert BrainStageRecord.model_validate_json(record.model_dump_json()).action == action
    assert "result" not in record.model_dump()
    with pytest.raises(ValidationError):
        BrainStageRecord(**{**record.model_dump(), "action": None})
    with pytest.raises(ValidationError):
        BrainStageRecord(**{**record.model_dump(), "action": Action(
            type="click", observation_id="old-obs", tab_id="tab-1", target_id="button-1")})


def test_async_task_events_preserve_snapshot_and_status_reason():
    base = {
        "event_id": "event-1", "task_id": "task-1", "run_id": "run-1",
        "kind": "plan_review", "snapshot_seq": 7,
        "observation_id": "obs-1", "plan_id": "plan-1", "plan_version": 2,
        "source_memory_ids": ["m-3"], "recorded_at": datetime(2026, 10, 14, tzinfo=timezone.utc),
    }
    scheduled = BrainTaskEvent(**{**base, "status": "scheduled"})
    completed = BrainTaskEvent(**{**base, "event_id": "event-2", "status": "completed",
                                  "output_record_ids": ["stage-7"]})
    assert scheduled.task_id == completed.task_id
    assert completed.snapshot_seq == 7
    assert BrainTaskEvent.model_validate_json(completed.model_dump_json()) == completed
    with pytest.raises(ValidationError):
        BrainTaskEvent(**{**base, "status": "failed"})
    with pytest.raises(ValidationError):
        BrainTaskEvent(**{**base, "status": "scheduled", "output_record_ids": ["stage-7"]})
    failed = BrainTaskEvent(**{**base, "event_id": "event-3", "status": "failed",
                               "reason_code": "provider_error"})
    assert failed.reason_code == "provider_error"


def test_memory_ids_and_sequences_are_not_reused_after_active_entry_removal():
    written = []

    class Writer:
        def write(self, value):
            written.append(value)

    store = MemoryStore("run-1", writer=Writer(), clock=lambda: 100.0)
    first = store.append("observation", "첫 화면")
    second = store.append("plan", "검색 계획", content_status="generated")
    store.entries.remove(first)
    third = store.append("reflection", "검색 결과를 확인한다.", content_status="generated",
                         based_on_seq=second.seq, source_stage_record_id="stage-9",
                         source_memory_ids=[first.memory_id])

    assert [first.seq, second.seq, third.seq] == [1, 2, 3]
    assert len({first.memory_id, second.memory_id, third.memory_id}) == 3
    assert third.schema_version == "2.0"
    assert third.source_stage_record_id == "stage-9"
    assert third.source_memory_ids == [first.memory_id]
    assert [row["memory_id"] for row in written] == [
        first.memory_id, second.memory_id, third.memory_id]

    legacy = {key: value for key, value in first.model_dump().items()
              if key not in {"schema_version", "source_stage_record_id", "source_memory_ids"}}
    restored = MemoryEntry.model_validate(legacy)
    assert restored.schema_version == "1.0"
    assert restored.source_memory_ids == []
    assert restored.source_stage_record_id is None


def test_memory_change_events_record_score_and_eviction_without_deleting_history():
    base = {
        "event_id": "memory-event-1", "run_id": "run-1", "memory_id": "m-1",
        "memory_seq": 1, "recorded_at": datetime(2026, 10, 14, tzinfo=timezone.utc),
    }
    scored = MemoryChangeEvent(
        **base, change="importance_scored", importance_after=8,
        source_stage_record_id="stage-importance-1",
    )
    evicted = MemoryChangeEvent(
        **{**base, "event_id": "memory-event-2"}, change="evicted",
        importance_before=8, retention_score=0.2, reason_code="capacity",
    )
    assert MemoryChangeEvent.model_validate_json(scored.model_dump_json()) == scored
    assert evicted.memory_id == scored.memory_id
    with pytest.raises(ValidationError):
        MemoryChangeEvent(**base, change="importance_scored")
    with pytest.raises(ValidationError):
        MemoryChangeEvent(**base, change="evicted", reason_code="capacity")


def test_active_memory_limit_accepts_configured_range():
    base = {
        "study_id": "study-1", "start_url": "https://example.test",
        "task": "상품 찾기", "allowed_origins": ["https://example.test"],
    }
    assert StudyConfig.model_validate(base).max_active_memories == 64
    assert StudyConfig.model_validate({**base, "max_active_memories": 12}).max_active_memories == 12
    with pytest.raises(ValidationError):
        StudyConfig.model_validate({**base, "max_active_memories": 9})
    with pytest.raises(ValidationError):
        StudyConfig.model_validate({**base, "max_active_memories": 65})
