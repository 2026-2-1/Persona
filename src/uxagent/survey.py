from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from .llm import (BudgetExceeded, BudgetManager, ClaudeProvider, GeminiProvider, JevProvider,
                  LocalQwenProvider, MockProvider, OpenAIProvider, estimate_cost_usd,
                  load_env_file, provider_for_model)
from .security import check_sensitive_input
from .call_evidence import call_evidence
from .storage import write_json


class SurveyQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: StrictStr = Field(min_length=1, max_length=100)
    type: Literal["multiple_choice", "short_text", "long_text"]
    prompt: StrictStr = Field(min_length=1, max_length=2000)
    options: list[StrictStr] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_options(self):
        if self.type == "multiple_choice" and not self.options:
            raise ValueError("multiple_choice questions require options")
        if self.type != "multiple_choice" and self.options:
            raise ValueError("options are only valid for multiple_choice questions")
        if len(set(self.options)) != len(self.options):
            raise ValueError("question options must be unique")
        return self


class Questionnaire(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    questionnaire_id: StrictStr = Field(min_length=1, max_length=100)
    title: StrictStr = Field(min_length=1, max_length=200)
    questions: list[SurveyQuestion] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_ids(self):
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("question IDs must be unique")
        return self


class SurveyAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question_id: StrictStr
    value: StrictStr | StrictInt | StrictFloat | StrictBool
    reason: StrictStr = Field(min_length=1, max_length=4000)


class SurveyMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    confidence_overall: StrictFloat = Field(ge=0, le=1)


class SurveyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    questionnaire_id: StrictStr
    answers: list[SurveyAnswer]
    meta: SurveyMeta


SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "survey.txt").read_text(encoding="utf-8")
DEFAULT_QUESTIONNAIRE = Path(__file__).resolve().parents[2] / "configs" / "survey.json"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _memory_trace(run: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    memories = _read_jsonl(run / "memory.jsonl")
    changes = _read_jsonl(run / "memory_changes.jsonl")
    importance: dict[str, int | None] = {}
    for event in changes:
        if event.get("change") == "importance_scored" and event.get("memory_id"):
            importance[event["memory_id"]] = event.get("importance_after")

    memories.sort(key=lambda row: (row.get("seq", 0), row.get("created_at", "")))
    trace = []
    provenance = []
    for row in memories:
        memory_id = row.get("memory_id")
        seq = row.get("seq")
        score = importance.get(memory_id, row.get("importance"))
        content = row.get("text", row.get("content", ""))
        timestamp = row.get("timestamp")
        if timestamp is None:
            timestamp = seq
        trace.append({"timestamp": timestamp, "kind": row.get("kind", "unknown"),
                      "importance": score, "content": content})
        provenance.append({"memory_id": memory_id, "seq": seq, "kind": row.get("kind"),
                           "importance": score, "source_step_ids": row.get("source_step_ids", []),
                           "created_at": row.get("created_at")})
    return trace, {"scope": "full_run_trace", "count": len(trace),
                   "memory_ids": [row.get("memory_id") for row in provenance],
                   "memories": provenance}


def _provider(name: str):
    providers = {"mock": MockProvider, "jev": JevProvider, "gemini": GeminiProvider,
                 "live": OpenAIProvider, "claude": ClaudeProvider, "gpu": LocalQwenProvider}
    try:
        return providers[name]()
    except KeyError:
        raise ValueError("unsupported survey provider") from None


def _validate_response(raw: str, questionnaire: Questionnaire) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("invalid_json") from None
    response = SurveyResponse.model_validate(parsed)
    if response.questionnaire_id != questionnaire.questionnaire_id:
        raise ValueError("questionnaire_id_mismatch")
    if [answer.question_id for answer in response.answers] != [question.id for question in questionnaire.questions]:
        raise ValueError("answer_question_mismatch")
    for question, answer in zip(questionnaire.questions, response.answers):
        if question.type == "multiple_choice" and answer.value not in question.options:
            raise ValueError("answer_option_invalid")
        if question.type != "multiple_choice" and not isinstance(answer.value, str):
            raise ValueError("text_answer_invalid")
    return response.model_dump(mode="json")


def _questionnaire_payload(form: Questionnaire) -> dict[str, Any]:
    payload = form.model_dump(mode="json", exclude={"questions": {index: {"options"}
                                for index, question in enumerate(form.questions)
                                if question.type != "multiple_choice"}})
    return payload


def _write_call(run: Path, record: dict[str, Any]):
    with (run / "llm_calls.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def _update_summary(run: Path, *, status: str, provider_name: str, model: str,
                    budget: BudgetManager | None = None):
    summary_path = run / "summary.json"
    if not summary_path.exists():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["survey"] = {"status": status, "provider": provider_name, "model": model,
                         "updated_at": datetime.now(timezone.utc).isoformat()}
    if budget is not None:
        summary["budget"] = budget.snapshot()
        summary["llm_request_count"] = budget.requests
        summary["llm_tokens"] = budget.tokens
        records = _read_jsonl(run / "llm_calls.jsonl")
        provider_usage: dict[str, dict[str, Any]] = {}
        for record in records:
            name = record.get("provider", "unknown")
            entry = provider_usage.setdefault(name, {
                "requests": 0, "input_tokens": 0, "output_tokens": 0,
                "estimated_cost_usd": 0.0, "cost_known": True,
            })
            entry["requests"] += 1
            if record.get("input_tokens") is None or record.get("output_tokens") is None:
                entry["cost_known"] = False
            else:
                entry["input_tokens"] += record["input_tokens"]
                entry["output_tokens"] += record["output_tokens"]
            cost = record.get("estimated_cost_usd")
            if cost is None:
                entry["cost_known"] = False
            else:
                entry["estimated_cost_usd"] += cost
        for entry in provider_usage.values():
            if not entry["cost_known"]:
                entry["estimated_cost_usd"] = None
            del entry["cost_known"]
        from .runner import measured_usage
        measured = measured_usage(records, budget.requests)
        for name, entry in measured["provider_usage"].items():
            provider_usage.setdefault(name, {}).update(entry)
        summary.update(measured)
        summary["provider_usage"] = provider_usage
        summary["cost"] = (sum(entry["estimated_cost_usd"] for entry in provider_usage.values())
                            if provider_usage and all(entry.get("estimated_cost_usd") is not None
                                                      for entry in provider_usage.values()) else None)
    write_json(summary_path, summary)


async def create_survey(run_dir: str | Path, questionnaire: Any | None = None, *,
                        provider=None, provider_name: str = "gpu") -> dict[str, Any]:
    load_env_file()
    run = Path(run_dir).resolve()
    started_at = datetime.now(timezone.utc).isoformat()
    run_record = json.loads((run / "run.json").read_text(encoding="utf-8")) if (run / "run.json").exists() else {}
    config = json.loads((run / "config.json").read_text(encoding="utf-8")) if (run / "config.json").exists() else {}
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8")) if (run / "summary.json").exists() else {}
    model = "persona-qwen" if provider_name == "gpu" else run_record.get("model", "mock-v1")
    raw_response = None
    parsed_response = None
    error = None
    usage: dict[str, Any] = {"provider": provider_name, "model": model, "input_tokens": None,
                             "output_tokens": None, "estimated_cost_usd": None}
    trace: list[dict[str, Any]] = []
    trace_provenance: dict[str, Any] = {"scope": "full_run_trace", "count": 0, "memory_ids": [], "memories": []}

    try:
        if questionnaire is None:
            questionnaire = json.loads(DEFAULT_QUESTIONNAIRE.read_text(encoding="utf-8"))
        check_sensitive_input(questionnaire)
    except FileNotFoundError:
        error = {"code": "questionnaire_not_found"}
    except ValueError:
        error = {"code": "sensitive_input_rejected"}
    except Exception:
        error = {"code": "invalid_questionnaire"}
    if error is None:
        try:
            form = Questionnaire.model_validate(questionnaire)
        except Exception as exc:
            message = str(exc)
            error = {"code": "empty_questionnaire" if "at least 1 item" in message else "invalid_questionnaire"}

    if error is None:
        try:
            trace, trace_provenance = _memory_trace(run)
        except Exception:
            error = {"code": "memory_trace_error"}
        if error is None and not trace:
            error = {"code": "empty_memory_trace"}

    if error is None:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(_questionnaire_payload(form), ensure_ascii=False)
             + "\n" + json.dumps(trace, ensure_ascii=False)},
        ]
        try:
            check_sensitive_input([message["content"] for message in messages])
        except ValueError:
            error = {"code": "sensitive_input_rejected"}

    budget = None
    call_attempted = False
    actual_provider = provider_name
    actual_model = model
    if error is None:
        model = "persona-qwen" if provider_name == "gpu" else run_record.get("model", "mock-v1")
        injected_provider = provider is not None
        provider = provider or _provider(provider_name)
        if provider_name != run_record.get("provider"):
            from .model_catalog import resolve_model
            model = resolve_model(provider_name)
        else:
            model = run_record.get("model", model)
        actual_model = (getattr(provider, "model", None) or model) if injected_provider else model
        actual_provider = provider_for_model(model, provider_name)
        prior_budget = summary.get("budget") or {}
        max_requests = prior_budget.get("max_requests", config.get("max_llm_requests"))
        max_tokens = prior_budget.get("max_tokens", config.get("max_total_tokens"))
        budget = BudgetManager(max_requests, max_tokens)
        budget.requests = int(prior_budget.get("requests", summary.get("llm_request_count", 0)) or 0)
        budget.tokens = int(prior_budget.get("tokens", summary.get("llm_tokens", 0)) or 0)
        budget.reserved_tokens = int(prior_budget.get("reserved_tokens", 0) or 0)
        reservation = config.get("max_output_tokens", 1200) + len(messages[1]["content"]) // 4
        try:
            budget.reserve(reservation)
        except BudgetExceeded as exc:
            error = {"code": "budget_exceeded", "reason": exc.reason_code,
                     "requested_tokens": reservation}
        if error is None:
            call_attempted = True
            started = time.monotonic()
            try:
                raw_response, usage = await provider.complete(
                    messages, actual_model, config.get("temperature", 0.2),
                    config.get("max_output_tokens", 1200))
            except Exception as exc:
                budget.settle(reservation, None)
                error = {"code": "provider_error", "reason": type(exc).__name__}
                _write_call(run, {
                    "module": "survey", "stage": "questionnaire", "provider": actual_provider,
                    "model": actual_model, "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "input_tokens": None, "output_tokens": None, "estimated": True,
                    "estimated_cost_usd": None, "error": type(exc).__name__,
                    **call_evidence("questionnaire", messages, {"memories": trace}),
                })
            else:
                usage = dict(usage or {})
                actual_provider = usage.get("provider") or provider_for_model(usage.get("model", actual_model), provider_name)
                actual_model = usage.get("model", actual_model)
                input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
                input_tokens = (input_tokens if isinstance(input_tokens, int) and not isinstance(input_tokens, bool)
                                and input_tokens >= 0 else None)
                output_tokens = (output_tokens if isinstance(output_tokens, int) and not isinstance(output_tokens, bool)
                                 and output_tokens >= 0 else None)
                valid_usage = input_tokens is not None and output_tokens is not None
                actual_tokens = input_tokens + output_tokens if valid_usage else None
                budget.settle(reservation, actual_tokens)
                cost = estimate_cost_usd(actual_provider, input_tokens, output_tokens, model=actual_model)
                usage = {"provider": actual_provider, "model": actual_model,
                         "input_tokens": input_tokens, "output_tokens": output_tokens,
                         "estimated_cost_usd": cost}
                try:
                    check_sensitive_input(raw_response)
                    parsed_response = _validate_response(raw_response, form)
                except Exception as exc:
                    if isinstance(exc, ValueError) and str(exc) == "sensitive_input_rejected":
                        raw_response = "[redacted: sensitive model output]"
                        error = {"code": "sensitive_output_rejected"}
                    else:
                        error = {"code": "invalid_json" if str(exc) == "invalid_json" else "invalid_model_response",
                                 "reason": str(exc) if str(exc) in {"invalid_json", "questionnaire_id_mismatch",
                                                                      "answer_question_mismatch", "answer_option_invalid",
                                                                      "text_answer_invalid"} else "schema_validation_failed"}
                call_record = {
                    "module": "survey", "stage": "questionnaire", "provider": actual_provider,
                    "model": actual_model, "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "input_tokens": input_tokens, "output_tokens": output_tokens,
                    "estimated": actual_tokens is None,
                    "estimated_cost_usd": cost,
                }
                call_record.update(call_evidence("questionnaire", messages,
                                                 {"memories": trace}, raw_response))
                if error:
                    call_record["error"] = ("invalid_json_response" if error["code"] == "invalid_json"
                                             else "model_output_error")
                _write_call(run, call_record)

    status = "completed" if error is None else error["code"]
    result = {
        "status": status, "questionnaire_id": form.questionnaire_id if error is None or "form" in locals() else None,
        "provider": actual_provider if call_attempted else provider_name,
        "model": actual_model, "usage": usage, "error": error,
        "questionnaire": (_questionnaire_payload(form) if "form" in locals() else
                          None if error and error["code"] == "sensitive_input_rejected" else questionnaire),
        "memory_trace": trace_provenance,
        "raw_response": raw_response, "parsed_response": parsed_response,
        "started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
    }

    if status == "completed":
        rows = []
        for question, answer in zip(form.questions, parsed_response["answers"]):
            rows.append({"question": question.prompt, "question_id": question.id,
                         "question_type": question.type,
                         "response": {"answer": answer["value"], "reason": answer["reason"],
                                      "data_type": "simulated_self_report",
                                      "source_step_ids": sorted({step for memory in trace_provenance["memories"]
                                                                  for step in memory["source_step_ids"]})},
                         "provenance": {"provider": actual_provider, "model": actual_model,
                                        "memory_scope": trace_provenance["scope"],
                                        "memory_ids": trace_provenance["memory_ids"]}})
        write_json(run / "survey.json", rows)
    else:
        # This compatibility file represents the latest attempt, not past success.
        (run / "survey.json").unlink(missing_ok=True)
    write_json(run / "survey_result.json", result)
    _update_summary(run, status=status, provider_name=actual_provider, model=actual_model, budget=budget)
    return result
