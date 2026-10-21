import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from uxagent import cli
from uxagent.survey import create_survey


ROOT = Path(__file__).resolve().parents[1]
QUESTIONNAIRE = {
    "questionnaire_id": "decathlon-v1",
    "title": "구매 탐색 경험",
    "questions": [
        {"id": "q1", "type": "multiple_choice", "prompt": "가격을 찾기 쉬웠나요?",
         "options": ["쉬웠다", "어려웠다", "기억나지 않는다"]},
        {"id": "q2", "type": "short_text", "prompt": "무엇이 어려웠나요?"},
    ],
}


def _make_run(folder, *, memories=None, changes=None, summary=None, budget=None):
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(json.dumps({
        "max_llm_requests": 20,
        "max_total_tokens": 100_000,
        "max_output_tokens": 500,
        "temperature": 0.2,
    }), encoding="utf-8")
    (folder / "run.json").write_text(json.dumps({"provider": "gpu", "model": "persona-qwen"}), encoding="utf-8")
    summary = summary or {"run_id": folder.name, "provider": "gpu", "model": "persona-qwen",
                         "llm_request_count": 2, "llm_tokens": 10,
                         "budget": {"requests": 2, "tokens": 10, "reserved_tokens": 0,
                                    "max_requests": 20, "max_tokens": 100_000},
                         "provider_usage": {"gpu": {"requests": 2, "input_tokens": 8,
                                                        "output_tokens": 2, "estimated_cost_usd": None}}}
    if budget:
        summary["budget"].update(budget)
    (folder / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    records = memories if memories is not None else [
        {"schema_version": "2.0", "memory_id": "m-1", "seq": 1, "kind": "observation",
         "text": "검색 결과에서 가격 필터를 찾기 어려웠다.", "timestamp": 1, "importance": None,
         "source_step_ids": [1], "created_at": "2026-10-18T00:00:00Z"},
        {"schema_version": "2.0", "memory_id": "m-2", "seq": 2, "kind": "thought",
         "text": "필터 메뉴를 열고 가격을 확인했다.", "timestamp": 2, "importance": 3,
         "source_step_ids": [2], "created_at": "2026-10-18T00:01:00Z"},
    ]
    (folder / "memory.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    (folder / "memory_changes.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in (changes or [])), encoding="utf-8")
    (folder / "llm_calls.jsonl").write_text("{}\n{}\n", encoding="utf-8")
    return folder


class SurveyProvider:
    model = "survey-test"

    def __init__(self, response=None, error=None):
        self.messages = []
        self.response = response or json.dumps({
            "questionnaire_id": "decathlon-v1",
            "answers": [
                {"question_id": "q1", "value": "어려웠다", "reason": "가격 필터를 찾기 어려웠다는 기억이 있다."},
                {"question_id": "q2", "value": "가격 필터 위치가 어려웠다.", "reason": "검색 중 가격 필터를 찾기 어려웠다."},
            ],
            "meta": {"confidence_overall": 0.8},
        }, ensure_ascii=False)
        self.error = error

    async def complete(self, messages, model, temperature, max_tokens):
        self.messages.append(messages)
        if self.error:
            raise self.error
        return self.response, {"provider": "gpu", "model": self.model,
                               "input_tokens": 32, "output_tokens": 18}


@pytest.mark.asyncio
async def test_long_gpu_survey_summarizes_full_trace_and_accounts_for_every_extra_call(tmp_path):
    from uxagent.llm import LocalQwenProvider
    memories = [{'schema_version': '2.0', 'memory_id': f'm-{i}', 'seq': i + 1,
                 'kind': 'thought', 'text': f'기억{i} ' + '러닝화 검색 가격 확인. ' * 20,
                 'timestamp': i, 'importance': 5, 'source_step_ids': [i + 1]}
                for i in range(80)]
    folder = _make_run(tmp_path / 'run', memories=memories, budget={'max_requests': 200})
    original = (folder / 'memory.jsonl').read_bytes()
    provider = LocalQwenProvider()
    final_requests = []

    async def enqueue(messages, model, temperature, max_tokens):
        assert provider.prompt_guard.fits(messages, max_tokens)
        if 'PROMPT_SUMMARY' in messages[0]['content']:
            raw = '{"summary":"생성된 기억에서 가격과 검색 경험을 회고했다. 실행 성공의 증거는 아니다."}'
        else:
            final_requests.append(messages)
            raw = SurveyProvider().response
        return raw, {'provider': 'gpu', 'model': model, 'input_tokens': 10, 'output_tokens': 10}

    provider._enqueue = enqueue
    result = await create_survey(folder, QUESTIONNAIRE, provider=provider)
    assert result['status'] == 'completed'
    assert result['memory_trace']['count'] == 80
    assert (folder / 'memory.jsonl').read_bytes() == original
    records = [json.loads(line) for line in (folder / 'llm_calls.jsonl').read_text().splitlines()][2:]
    assert sum(row['stage'] == 'prompt_summary' for row in records) > 1
    assert records[-1]['stage'] == 'questionnaire'
    assert records[-1]['prompt_guard']['checked'] is True
    summary = json.loads((folder / 'summary.json').read_text())
    assert summary['budget']['requests'] == 2 + len(records)
    assert summary['budget']['reserved_tokens'] == 0
    assert json.loads(final_requests[0][1]['content'].splitlines()[0])['questions'][0]['options'] == QUESTIONNAIRE['questions'][0]['options']


def test_survey_sends_questionnaire_and_full_append_only_trace_and_preserves_provenance(tmp_path):
    async def run():
        old = {"schema_version": "2.0", "memory_id": "m-1", "seq": 1, "kind": "observation",
               "text": "오래된 기억도 전체 trace에 포함된다.", "timestamp": 1, "importance": None,
               "source_step_ids": [1], "created_at": "2026-10-18T00:00:00Z"}
        current = {"schema_version": "2.0", "memory_id": "m-2", "seq": 2, "kind": "thought",
                   "text": "현재 기억.", "timestamp": 2, "importance": 3,
                   "source_step_ids": [2], "created_at": "2026-10-18T00:01:00Z"}
        changes = [
            {"memory_id": "m-1", "memory_seq": 1, "change": "importance_scored", "importance_after": 8},
            {"memory_id": "m-1", "memory_seq": 1, "change": "evicted", "importance_before": 8},
        ]
        folder = _make_run(tmp_path / "run", memories=[old, current], changes=changes,
                            summary={"run_id": "run", "provider": "gpu", "model": "persona-qwen",
                                     "verification": "success", "llm_request_count": 2, "llm_tokens": 10,
                                     "budget": {"requests": 2, "tokens": 10, "reserved_tokens": 0,
                                                "max_requests": 20, "max_tokens": 100_000},
                                     "provider_usage": {"gpu": {"requests": 2, "input_tokens": 8,
                                                                    "output_tokens": 2, "estimated_cost_usd": None}}})
        provider = SurveyProvider()
        result = await create_survey(folder, QUESTIONNAIRE, provider=provider)

        user_input = provider.messages[0][1]["content"]
        questionnaire_text, trace_text, _ = user_input.split("\n", 2)
        trace = json.loads(trace_text)
        assert json.loads(questionnaire_text) == QUESTIONNAIRE
        assert [item["content"] for item in trace] == [old["text"], current["text"]]
        assert trace[0]["importance"] == 8
        assert len(result["memory_trace"]["memory_ids"]) == 2
        assert result["status"] == "completed"
        assert result["provider"] == "gpu" and result["model"] == "survey-test"

        rows = json.loads((folder / "survey.json").read_text(encoding="utf-8"))
        assert rows[0]["response"]["answer"] == "어려웠다"
        assert rows[0]["response"]["data_type"] == "simulated_self_report"
        stored = json.loads((folder / "survey_result.json").read_text(encoding="utf-8"))
        assert stored["raw_response"] == provider.response
        assert stored["parsed_response"]["questionnaire_id"] == "decathlon-v1"
        assert stored["memory_trace"]["scope"] == "full_run_trace"

        summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        calls = [json.loads(line) for line in (folder / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()]
        assert summary["llm_request_count"] == 3
        assert summary["llm_tokens"] == summary["budget"]["tokens"] == 60
        assert calls[-1]["module"] == "survey" and calls[-1]["estimated_cost_usd"] is None
        assert summary["verification"] == "success"
    import asyncio
    asyncio.run(run())


def _failed_execution(folder):
    step = {'step_id': 1, 'action': {'type': 'click', 'target_id': 'running'},
            'result': {'ok': False, 'error': {'code': 'action_timeout', 'message': 'Popup intercepted click'},
                       'url_before': 'https://shop.test/', 'url_after': 'https://shop.test/'}}
    (folder / 'steps.jsonl').write_text(json.dumps(step) + '\n')


def test_survey_separates_generated_memories_from_executed_failures(tmp_path):
    import asyncio
    folder = _make_run(tmp_path / 'facts', memories=[{
        'memory_id': 'm-generated', 'seq': 1, 'timestamp': 1, 'kind': 'thought',
        'content_status': 'generated', 'text': '클릭에 성공했고 필터가 직관적이었다.'}])
    _failed_execution(folder)
    response = json.loads(SurveyProvider().response)
    response['meta']['execution_error_count'] = 1
    provider = SurveyProvider(response=json.dumps(response, ensure_ascii=False))
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE, provider=provider))
    parts = provider.messages[0][1]['content'].split('\n')
    memories = json.loads(parts[1])
    assert memories[0]['content_status'] == 'generated'
    facts = json.loads(parts[2])['execution_trace']
    assert facts['steps'][0]['ok'] is False
    assert facts['error_count'] == 1
    assert facts['steps'][0]['error']['code'] == 'action_timeout'
    assert 'verification' not in json.dumps(facts)
    assert 'evaluation_expectations' not in provider.messages[0][1]['content']
    assert result['status'] == 'completed'
    assert result['grounding']['execution_errors_validated'] is True


@pytest.mark.parametrize('reported', [None, 0, 2])
def test_survey_cannot_claim_no_execution_errors_when_a_click_failed(tmp_path, reported):
    import asyncio
    folder = _make_run(tmp_path / 'contradiction')
    _failed_execution(folder)
    response = json.loads(SurveyProvider().response)
    if reported is not None:
        response['meta']['execution_error_count'] = reported
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE,
        provider=SurveyProvider(response=json.dumps(response))))
    assert result['status'] == 'invalid_model_response'
    assert result['error']['reason'] == 'execution_fact_mismatch'
    assert not (folder / 'survey.json').exists()


def test_failed_survey_rerun_archives_old_answers_instead_of_showing_them_as_current(tmp_path):
    import asyncio
    folder = _make_run(tmp_path / 'rerun')
    old = [{'question': '이전 질문', 'response': {'answer': '이전 답변'}}]
    (folder / 'survey.json').write_text(json.dumps(old, ensure_ascii=False))
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE, provider=SurveyProvider(response='invalid')))
    assert result['status'] == 'invalid_json'
    assert not (folder / 'survey.json').exists()
    archived = list(folder.glob('survey.previous-*.json'))
    assert len(archived) == 1 and json.loads(archived[0].read_text()) == old


def test_execution_trace_secrets_are_rejected_before_model_call(tmp_path):
    import asyncio
    folder = _make_run(tmp_path / 'execution-secret')
    step = {'step_id': 1, 'action': {'type': 'type', 'text': 'password=do-not-send'},
            'result': {'ok': True}}
    (folder / 'steps.jsonl').write_text(json.dumps(step) + '\n')
    provider = SurveyProvider()
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE, provider=provider))
    assert result['status'] == 'sensitive_input_rejected'
    assert not provider.messages
    assert 'do-not-send' not in (folder / 'survey_result.json').read_text()


@pytest.mark.parametrize(("questionnaire", "memories", "code"), [
    ({"questionnaire_id": "empty", "title": "Empty", "questions": []}, None, "empty_questionnaire"),
    (QUESTIONNAIRE, [], "empty_memory_trace"),
])
def test_empty_questionnaire_and_trace_are_distinct_and_do_not_call_provider(tmp_path, questionnaire, memories, code):
    import asyncio
    folder = _make_run(tmp_path / code, memories=memories)
    provider = SurveyProvider()
    result = asyncio.run(create_survey(folder, questionnaire, provider=provider))
    assert result["status"] == code
    assert not provider.messages
    assert not (folder / "survey.json").exists()


def test_invalid_json_is_saved_as_raw_failure_not_as_survey_answers(tmp_path):
    import asyncio
    folder = _make_run(tmp_path / "invalid")
    provider = SurveyProvider(response="not json")
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE, provider=provider))
    assert result["status"] == "invalid_json"
    assert result["raw_response"] == "not json"
    assert not (folder / "survey.json").exists()
    call = json.loads((folder / "llm_calls.jsonl").read_text().splitlines()[-1])
    assert call["error"] == "invalid_json_response"


def test_semantically_invalid_json_is_not_rendered_as_a_successful_survey(tmp_path):
    import asyncio
    folder = _make_run(tmp_path / "invalid-schema")
    response = json.dumps({
        "questionnaire_id": "decathlon-v1",
        "answers": [
            {"question_id": "q1", "value": "not an option", "reason": "bad"},
            {"question_id": "q2", "value": "text", "reason": "ok"},
        ],
        "meta": {"confidence_overall": 0.5},
    })
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE, provider=SurveyProvider(response=response)))
    assert result["status"] == "invalid_model_response"
    assert result["raw_response"] == response
    assert not (folder / "survey.json").exists()


def test_provider_error_logs_attempt_without_leaking_exception_text(tmp_path):
    import asyncio
    folder = _make_run(tmp_path / "provider-error")
    provider = SurveyProvider(error=RuntimeError("password=top-secret"))
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE, provider=provider))
    assert result["status"] == "provider_error"
    assert "top-secret" not in json.dumps(result)
    logs = (folder / "llm_calls.jsonl").read_text(encoding="utf-8")
    assert "top-secret" not in logs
    assert json.loads(logs.splitlines()[-1])["error"] == "RuntimeError"
    assert json.loads((folder / "summary.json").read_text())["llm_request_count"] == 3


def test_survey_budget_exhaustion_is_recorded_without_provider_call(tmp_path):
    import asyncio
    folder = _make_run(tmp_path / "budget", budget={"requests": 20, "max_requests": 20})
    provider = SurveyProvider()
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE, provider=provider))
    assert result["status"] == "budget_exceeded"
    assert not provider.messages
    assert not (folder / "survey.json").exists()


def test_survey_budget_also_reserves_system_instructions(tmp_path):
    import asyncio
    folder = _make_run(tmp_path / 'system-budget', budget={'max_tokens': 900})
    provider = SurveyProvider()
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE, provider=provider))
    assert result['status'] == 'budget_exceeded'
    assert not provider.messages


def test_sensitive_questionnaire_is_rejected_before_prompt_or_log_storage(tmp_path):
    import asyncio
    folder = _make_run(tmp_path / "sensitive")
    provider = SurveyProvider()
    questionnaire = {**QUESTIONNAIRE, "title": "password=top-secret"}
    result = asyncio.run(create_survey(folder, questionnaire, provider=provider))
    assert result["status"] == "sensitive_input_rejected"
    assert result["questionnaire"] is None
    assert not provider.messages
    assert "top-secret" not in (folder / "survey_result.json").read_text(encoding="utf-8")
    assert len((folder / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_sensitive_content_in_memory_trace_is_not_sent_or_copied_to_survey_result(tmp_path):
    import asyncio
    secret = "password=do-not-send"
    folder = _make_run(tmp_path / "sensitive-memory", memories=[{
        "schema_version": "2.0", "memory_id": "m-sensitive", "seq": 1, "kind": "observation",
        "text": secret, "timestamp": 1, "importance": None, "source_step_ids": [1],
    }])
    provider = SurveyProvider()
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE, provider=provider))
    assert result["status"] == "sensitive_input_rejected"
    assert not provider.messages
    assert secret not in (folder / "survey_result.json").read_text(encoding="utf-8")


def test_large_trace_is_not_silently_truncated_when_token_budget_is_too_small(tmp_path):
    import asyncio
    folder = _make_run(tmp_path / "large", budget={"max_tokens": 600})
    provider = SurveyProvider()
    result = asyncio.run(create_survey(folder, QUESTIONNAIRE, provider=provider))
    assert result["status"] == "budget_exceeded"
    assert result["error"]["reason"] == "token_limit"
    assert result["error"]["requested_tokens"] > 600
    assert not provider.messages


def test_batch_runs_every_session_before_surveys_and_keeps_later_results_after_one_survey_fails(tmp_path, monkeypatch):
    import asyncio
    from argparse import Namespace

    events = []
    study = ROOT / "configs/study.json"
    personas = tmp_path / "personas.jsonl"
    raw_persona = json.loads((ROOT / "configs/persona.json").read_text(encoding="utf-8"))
    personas.write_text("".join(json.dumps({**raw_persona, "persona_id": f"p-{i}"}) + "\n" for i in (1, 2)), encoding="utf-8")

    async def fake_run(*args, **kwargs):
        index = len([event for event in events if event.startswith("run-terminated")]) + 1
        events.append(f"run-terminated-{index}")
        run_dir = tmp_path / f"run-{index}"
        run_dir.mkdir()
        (run_dir / "summary.json").write_text(json.dumps({
            "llm_request_count": 1, "llm_tokens": 3,
        }), encoding="utf-8")
        return run_dir, {"run_id": f"run-{index}", "termination_reason": "agent_finished",
                         "verification": "unknown", "llm_request_count": 1, "llm_tokens": 3}

    async def fake_survey(run_dir, questionnaire=None, provider=None, provider_name=None):
        run_dir = Path(run_dir)
        run_name = run_dir.name
        events.append(f"survey-{run_name}")
        if run_name == "run-1":
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            summary.update(llm_request_count=2, llm_tokens=8)
            (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            return {"status": "provider_error", "error": {"code": "RuntimeError"}}
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        summary.update(llm_request_count=2, llm_tokens=8)
        (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return {"status": "completed", "usage": {"requests": 1, "tokens": 5}}

    monkeypatch.setattr(cli, "run_study", fake_run)
    monkeypatch.setattr(cli, "create_survey", fake_survey)
    args = Namespace(personas=str(personas), stop_file=None, study=str(study), provider="gpu",
                     survey_provider=None, questionnaire=None, output=str(tmp_path / "runs"))
    assert asyncio.run(cli._batch(args)) == 0
    assert events == ["run-terminated-1", "run-terminated-2", "survey-run-1", "survey-run-2"]
    batch = json.loads((tmp_path / "runs/batch_summary.json").read_text(encoding="utf-8"))
    assert [row["survey_status"] for row in batch["runs"]] == ["provider_error", "completed"]
    assert batch["llm_request_count"] == 4 and batch["llm_tokens"] == 16
