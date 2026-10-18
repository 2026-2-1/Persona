import json
import csv
import io

from uxagent.call_evidence import call_evidence
from uxagent.monitor import Dashboard
from uxagent.reports import export_report


def test_call_evidence_keeps_u_request_response_retrieval_and_method():
    messages = [{"role": "system", "content": "U planning"},
                {"role": "user", "content": '{"memories": ["m1"]}'}]
    payload = {"memories": [{"memory_id": "m1", "text": "old search"}]}

    evidence = call_evidence("plan", messages, payload, '{"plan":"continue"}')

    assert evidence["schema_version"] == "2.0"
    assert evidence["method_name"] == "planning"
    assert evidence["recorded_at"].endswith("+00:00")
    assert evidence["request"] == messages
    assert evidence["response"] == '{"plan":"continue"}'
    assert evidence["retrieve_result"] == payload["memories"]
    assert evidence["call_id"].startswith("call-")


def test_call_evidence_redacts_credential_bearing_payload(monkeypatch):
    secret = "actual-test-api-secret-value"
    monkeypatch.setenv("PERSONA_TEST_API_KEY", secret)

    evidence = call_evidence("decision", [{"role": "user", "content": secret}],
                             {"recent_memories": [secret]}, secret)

    assert evidence["evidence_redacted"] is True
    assert secret not in json.dumps(evidence)
    assert evidence["request"] == "[redacted: sensitive input]"
    assert evidence["response"] == "[redacted: sensitive output]"


def test_dashboard_does_not_expose_local_raw_call_evidence(tmp_path):
    folder = tmp_path / "runs" / "private-run"
    folder.mkdir(parents=True)
    (folder / "run.json").write_text('{"run_id":"private-run"}', encoding="utf-8")
    (folder / "summary.json").write_text(json.dumps({"verification": "success"}), encoding="utf-8")
    (folder / "final_evaluation.json").write_text(json.dumps({
        "termination_reason": "agent_finished", "observation_id": "obs-final",
        "evaluation": {"verification": "success"},
    }), encoding="utf-8")
    raw_request = [{"role": "user", "content": "private prompt text"}]
    (folder / "llm_calls.jsonl").write_text(json.dumps({
        "schema_version": "2.0", "module": "fast", "stage": "plan",
        "request": raw_request, "response": "private raw response",
        "retrieve_result": [{"text": "private memory"}],
    }) + "\n", encoding="utf-8")

    detail = Dashboard(tmp_path / "runs").run_detail("private-run")

    assert detail["calls"][0]["stage"] == "plan"
    assert "request" not in detail["calls"][0]
    assert "response" not in detail["calls"][0]
    assert "retrieve_result" not in detail["calls"][0]
    assert detail["final_evaluation"]["observation_id"] == "obs-final"
    assert json.loads(export_report(detail, "json"))["final_evaluation"]["observation_id"] == "obs-final"
    rows = list(csv.DictReader(io.StringIO(export_report(detail, "csv"))))
    assert any(row["record_type"] == "final_evaluation"
               and json.loads(row["brain_record"])["observation_id"] == "obs-final" for row in rows)
