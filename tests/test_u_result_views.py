"""U results must remain distinct from human reviews and legacy records."""
import csv
import io
import json

import pytest

from uxagent.monitor import Dashboard
from uxagent.reports import export_report
from uxagent.review import create_review


def put(folder, name, value):
    (folder / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def rows(folder, name, values):
    (folder / name).write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values), encoding="utf-8")


@pytest.fixture
def u_folder(tmp_path):
    folder = tmp_path / "runs" / "u-review"
    folder.mkdir(parents=True)
    put(folder, "run.json", {"run_id": folder.name, "provider": "mock", "execution_mode": "ai",
                              "source_kind": "synthetic_fixture", "wonder_policy": "u_every_cycle"})
    put(folder, "config.json", {"task": "합성 상품의 상세 정보를 확인하세요."})
    put(folder, "persona.json", {})
    put(folder, "summary.json", {"run_id": folder.name, "termination_reason": "agent_finished",
                                  "verification": "failure", "evaluator": {"feature_checks": [
                                      {"id": "detail", "label": "상세 확인", "status": "fail"}]}})
    rows(folder, "steps.jsonl", [{"step_id": 1, "observation_id": "obs-before",
                                  "next_observation_id": "obs-before", "verification": "unknown",
                                  "evaluation": {"reason": "deferred_until_run_end"}}])
    put(folder, "final_evaluation.json", {"termination_reason": "agent_finished", "termination_step_id": 1,
                                          "observation_id": "obs-final", "url": "https://fixture.test/final",
                                          "observed_at": "2026-10-18T00:00:00Z",
                                          "evaluation": {"verification": "failure", "reason": "detail_mismatch"}})
    observations = folder / "observations"
    observations.mkdir()
    put(observations, "obs-final.json", {"observation_id": "obs-final", "html": "최종 실패 화면"})
    rows(folder, "brain_stages.jsonl", [
        {"schema_version": "1.0", "run_id": folder.name, "record_id": "wonder-1", "task_id": "slow-1",
         "stage": "wonder", "text": '{"thoughts":["합성 생각 A","합성 생각 B"]}',
         "model_response": {"thoughts": ["합성 생각 A", "합성 생각 B"]}},
        {"schema_version": "1.0", "run_id": folder.name, "record_id": "wonder-empty", "task_id": "slow-2",
         "stage": "wonder", "text": '{"thoughts":[]}', "model_response": {"thoughts": []}},
    ])
    rows(folder, "memory.jsonl", [{"schema_version": "2.0", "run_id": folder.name,
                                   "memory_id": "thought-a", "seq": 1, "kind": "thought", "text": "합성 생각 A",
                                   "source_stage_record_id": "wonder-1"}])
    return folder


def completed_survey(folder):
    put(folder, "survey_result.json", {
        "status": "completed", "questionnaire_id": "form-1", "provider": "gpu", "model": "persona-qwen",
        "raw_response": "LOCAL_RESPONSE_ONLY", "request": "LOCAL_REQUEST_ONLY",
        "questionnaire": {"questionnaire_id": "form-1", "title": "합성 설문", "questions": [
            {"id": "q1", "type": "short_text", "prompt": "어떤 점이 어려웠나요?"}]},
        "parsed_response": {"questionnaire_id": "form-1", "answers": [
            {"question_id": "q1", "value": "합성 설문 답변", "reason": "합성 근거"}],
            "meta": {"confidence_overall": 0.5}},
        "memory_trace": {"memory_ids": ["thought-a"], "memories": [{"source_step_ids": [1]}]},
    })
    put(folder, "survey.json", [{"question": "어떤 점이 어려웠나요?", "question_id": "q1",
                                  "response": {"answer": "합성 설문 답변", "data_type": "simulated_self_report"}}])


def test_u_wonder_counts_actual_thoughts_and_stored_history(u_folder):
    detail = Dashboard(u_folder.parent).run_detail(u_folder.name)
    wonder = detail["wonder"]
    assert wonder["policy"] == "u_every_cycle"
    assert wonder["probability_unit"] is None
    assert wonder["responses"] == 2 and wonder["empty_responses"] == 1
    assert [r["text"] for r in wonder["thoughts"]] == ["합성 생각 A", "합성 생각 B"]
    assert [r["stored"] for r in wonder["thoughts"]] == [True, False]
    for kind in ("md", "html"):
        output = export_report(detail, kind)
        assert "1%" not in output
        assert "매 반복" in output


def test_completed_survey_is_projected_into_all_formats_without_raw_call_evidence(u_folder):
    completed_survey(u_folder)
    detail = Dashboard(u_folder.parent).run_detail(u_folder.name)
    assert detail["survey"]["status"] == "completed"
    assert detail["survey"]["data_type"] == "simulated_self_report"
    assert detail["survey"]["answers"][0]["answer"] == "합성 설문 답변"
    for kind in ("json", "csv", "md", "html"):
        output = export_report(detail, kind)
        assert "합성 설문 답변" in output
        assert "LOCAL_RESPONSE_ONLY" not in output and "LOCAL_REQUEST_ONLY" not in output
    records = list(csv.DictReader(io.StringIO(export_report(detail, "csv"))))
    assert any(r["record_type"] == "survey" for r in records)


def test_failed_current_survey_does_not_publish_stale_success_answers(u_folder):
    completed_survey(u_folder)
    put(u_folder, "survey_result.json", {"status": "invalid_json", "error": {"code": "invalid_json"},
                                         "raw_response": "LOCAL_FAILURE_ONLY"})
    detail = Dashboard(u_folder.parent).run_detail(u_folder.name)
    assert detail["survey"]["status"] == "invalid_json"
    assert detail["survey"]["answers"] == []
    for kind in ("json", "csv", "md", "html"):
        assert "합성 설문 답변" not in export_report(detail, kind)
    # Reading is non-destructive; the producer's old file is not rewritten.
    assert "합성 설문 답변" in (u_folder / "survey.json").read_text(encoding="utf-8")


def test_legacy_survey_is_marked_as_unverified_generation_format(u_folder):
    put(u_folder, "survey.json", [{"question": "이전 질문", "response": {"answer": "이전 답변"}}])
    detail = Dashboard(u_folder.parent).run_detail(u_folder.name)
    assert detail["survey"]["status"] == "legacy"
    assert detail["survey"]["data_type"] == "legacy_or_unknown"
    assert detail["survey"]["answers"][0]["answer"] == "이전 답변"


@pytest.mark.parametrize('raw', ['null', '[]', '{broken'])
def test_malformed_current_survey_never_falls_back_to_old_answers(u_folder, raw):
    completed_survey(u_folder)
    (u_folder / 'survey_result.json').write_text(raw, encoding='utf-8')
    view = Dashboard(u_folder.parent).run_detail(u_folder.name)['survey']
    assert view['status'] == 'invalid_record'
    assert view['answers'] == []


def test_final_checkpoint_links_actual_final_observation_and_versions_that_evidence(u_folder):
    dashboard = Dashboard(u_folder.parent)
    before = dashboard.run_detail(u_folder.name)
    card = before["cards"][0]
    assert card["evidence_observation_ids"] == ["obs-final"]
    put(u_folder / "observations", "obs-final.json", {"observation_id": "obs-final", "html": "수정된 최종 근거"})
    after = dashboard.run_detail(u_folder.name)
    assert after["cards"][0]["card_version"] != card["card_version"]
    assert before["summary"]["verification"] == "failure"
    for kind in ("json", "csv", "md", "html"):
        assert "obs-final" in export_report(after, kind)


def test_cli_review_keeps_raw_call_evidence_out_of_html(u_folder):
    rows(u_folder, "llm_calls.jsonl", [{"stage": "plan", "model": "mock-v1", "input_tokens": 1,
                                       "request": "PRIVATE_PROMPT", "response": "PRIVATE_RESPONSE",
                                       "retrieve_result": ["PRIVATE_RETRIEVAL"]}])
    path, _ = create_review(u_folder)
    output = path.read_text(encoding="utf-8")
    assert "mock-v1" in output
    for value in ("PRIVATE_PROMPT", "PRIVATE_RESPONSE", "PRIVATE_RETRIEVAL"):
        assert value not in output
