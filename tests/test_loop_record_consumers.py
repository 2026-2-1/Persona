import csv
import io
import json

from uxagent.monitor import Dashboard
from uxagent.reports import export_report


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_run_detail_and_exports_preserve_stage_task_and_removed_memory_evidence(tmp_path):
    folder = tmp_path / "runs" / "trace-run"
    folder.mkdir(parents=True)
    (folder / "run.json").write_text(json.dumps({"run_id": "trace-run", "provider": "mock"}), encoding="utf-8")
    (folder / "summary.json").write_text(json.dumps({"verification": "unknown", "termination_reason": "cancelled"}), encoding="utf-8")
    _write_jsonl(folder / "steps.jsonl", [{"step_id": 1, "observation_id": "obs-1", "next_observation_id": "obs-2",
        "action": {"type": "click"}, "result": {"ok": True}, "verification": "unknown",
        "evaluation": {"verification": "unknown", "reason": "not_evaluated"}, "memory_ids": ["m-old"]}])
    _write_jsonl(folder / "brain_stages.jsonl", [{"record_id": "p1", "stage": "perception", "observation_id": "obs-1",
        "text": "AI 화면 해석", "source_memory_ids": ["m-old"], "content_status": "generated"},
        {"record_id": "r1", "stage": "reflection", "task_id": "slow-1", "observation_id": "obs-1",
         "text": "AI 성찰", "source_memory_ids": ["m-old"], "content_status": "generated"},
        {"record_id": "w1", "stage": "wonder", "task_id": "wonder-1", "observation_id": None,
         "text": "AI 가정", "source_memory_ids": [], "content_status": "generated"}])
    _write_jsonl(folder / "brain_tasks.jsonl", [{"task_id": "slow-1", "kind": "reflection", "status": "scheduled",
        "observation_id": "obs-1"}, {"task_id": "slow-1", "kind": "reflection", "status": "completed",
        "observation_id": "obs-1"}, {"task_id": "slow-2", "kind": "plan_review", "status": "cancelled",
        "observation_id": "obs-1"}, {"task_id": "wonder-1", "kind": "wonder", "status": "completed",
        "observation_id": None}])
    _write_jsonl(folder / "wonder_draws.jsonl", [{"parent_task_id": "slow-1", "wonder_task_id": "wonder-1",
        "parent_kind": "reflection", "selected": True}])
    _write_jsonl(folder / "memory.jsonl", [{"memory_id": "m-old", "kind": "observation", "text": "원본 기억",
        "content_status": "observed", "source_observation_ids": ["obs-1"]}])
    _write_jsonl(folder / "memory_changes.jsonl", [{"memory_id": "m-old", "change": "evicted", "reason_code": "capacity"}])

    dashboard = Dashboard(tmp_path / "runs", tmp_path / "personas", "configs/study.json")
    detail = dashboard.run_detail("trace-run")
    assert [row["status"] for row in detail["brain_tasks"]] == ["scheduled", "completed", "cancelled", "completed"]
    assert detail["trace"][0]["stages"][0]["stage"] == "perception"
    assert any(row["stage"] == "wonder" for row in detail["trace"][0]["stages"])
    assert any(row["kind"] == "wonder" for row in detail["trace"][0]["tasks"])
    assert detail["trace"][0]["memories"][0]["memory_id"] == "m-old"
    assert detail["trace"][0]["memories"][0]["removed"] is True
    assert detail["trace"][0]["memories"][0]["text"] == "원본 기억"
    for kind in ("json", "csv", "md", "html"):
        output = export_report(detail, kind)
        assert "AI 화면 해석" in output
        assert "cancelled" in output
        assert "m-old" in output
    assert json.loads(export_report(detail, "json"))["summary"]["verification"] == "unknown"
    records = list(csv.reader(io.StringIO(export_report(detail, "csv"))))
    assert any(row[7] == "brain_stage" for row in records)
    assert any(row[7] == "step" for row in records)
    assert "독립 판정 unknown" in export_report(detail, "md")


def test_legacy_null_step_has_empty_trace_and_exports(tmp_path):
    folder = tmp_path / "runs" / "legacy"
    folder.mkdir(parents=True)
    (folder / "run.json").write_text('{"run_id":"legacy"}', encoding="utf-8")
    _write_jsonl(folder / "steps.jsonl", [{"step_id": 1, "observation_id": "obs-1", "action": None, "result": None}])
    dashboard = Dashboard(tmp_path / "runs", tmp_path / "personas", "configs/study.json")
    detail = dashboard.run_detail("legacy")
    assert detail["trace"][0]["stages"] == []
    assert detail["trace"][0]["tasks"] == []
    assert detail["trace"][0]["memories"] == []
    for kind in ("json", "csv", "md", "html"):
        assert export_report(detail, kind)
