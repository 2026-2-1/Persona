"""Read-only public views of simulated surveys and U/legacy Wonder results."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .security import check_sensitive_input
from .survey import Questionnaire, _validate_response


def _read(path):
    if path.is_symlink():
        return None, "unsafe_record"
    if not path.exists():
        return None, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value, "invalid_record" if value is None else None
    except (OSError, ValueError, UnicodeError):
        return None, "invalid_record"


def survey_view(folder: Path):
    """Never promote an older answer file over the latest failed model attempt."""
    result, error = _read(folder / "survey_result.json")
    view = {"status": error or "not_recorded", "data_type": "legacy_or_unknown", "answers": []}
    if error:
        return view
    if result is not None:
        view["data_type"] = "simulated_self_report"
        if not isinstance(result, dict) or not re.fullmatch(r"[a-z_]{1,80}", str(result.get("status", ""))):
            view["status"] = "invalid_record"
            return view
        view["status"] = result["status"]
        for key in ("questionnaire_id", "provider", "model", "started_at", "finished_at"):
            if isinstance(result.get(key), str):
                view[key] = result[key]
        if result["status"] == "completed":
            try:
                form = Questionnaire.model_validate(result.get("questionnaire"))
                response = _validate_response(json.dumps(result.get("parsed_response")), form)
                trace = result.get("memory_trace") or {}
                memory_ids = [v for v in trace.get("memory_ids", []) if isinstance(v, str)]
                steps = sorted({v for row in trace.get("memories", []) if isinstance(row, dict)
                                for v in row.get("source_step_ids", [])
                                if isinstance(v, int) and not isinstance(v, bool)})
                view["answers"] = [{"question_id": question.id, "question": question.prompt,
                                    "question_type": question.type, "answer": answer["value"],
                                    "reason": answer["reason"], "source_step_ids": steps,
                                    "memory_ids": memory_ids}
                                   for question, answer in zip(form.questions, response["answers"])]
            except (TypeError, ValueError, AttributeError):
                view.update(status="invalid_record", answers=[])
        else:
            code = (result.get("error") or {}).get("code") if isinstance(result.get("error"), dict) else None
            if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,80}", code):
                view["error"] = {"code": code}
    else:
        legacy, error = _read(folder / "survey.json")
        if error:
            view["status"] = error
        elif legacy is not None:
            if not isinstance(legacy, list):
                view["status"] = "invalid_record"
            else:
                view["status"] = "legacy"
                for row in legacy:
                    if not isinstance(row, dict) or not isinstance(row.get("question"), str):
                        view.update(status="invalid_record", answers=[])
                        break
                    response = row.get("response")
                    if not isinstance(response, dict) or not isinstance(response.get("answer"), (str, int, float, bool)):
                        view.update(status="invalid_record", answers=[])
                        break
                    view["answers"].append({"question": row["question"], "answer": response["answer"],
                                            "reason": response.get("reason") if isinstance(response.get("reason"), str) else ""})
    try:
        check_sensitive_input(view)
    except ValueError:
        view = {"status": "sensitive_record", "data_type": view["data_type"], "answers": []}
    return view


def wonder_view(run, stages, memories, draws):
    thoughts = []
    responses = empty = 0
    warnings = []
    is_u = run.get("wonder_policy") == "u_every_cycle"
    for record in stages:
        if record.get("stage") != "wonder":
            continue
        response = record.get("model_response")
        if response is None:
            try:
                response = json.loads(record["text"])
            except (ValueError, KeyError, TypeError):
                response = None
        u_response = isinstance(response, dict) and "thoughts" in response
        is_u = is_u or u_response
        texts = response.get("thoughts") if u_response else [record.get("text", "")]
        if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
            warnings.append({"record_id": record.get("record_id"), "reason": "invalid_thoughts"})
            continue
        responses += 1
        empty += not texts
        for index, text in enumerate(texts):
            matches = [entry for entry in memories
                       if entry.get("kind") == ("thought" if u_response else "wonder")
                       and entry.get("source_stage_record_id") == record.get("record_id")
                       and (entry.get("text") == text or not u_response and "text" not in entry)]
            thoughts.append({"task_id": record.get("task_id"), "record_id": record.get("record_id"),
                             "thought_index": index, "text": text, "stored": bool(matches),
                             "memory_ids": [entry["memory_id"] for entry in matches],
                             "active": any(not entry.get("evicted") for entry in matches),
                             "source_type": "generated_assumption"})
    policy = "u_every_cycle" if is_u else "legacy_draw" if draws or thoughts else "unknown"
    description = ("매 반복의 Wonder 응답입니다. 실제 사용자 기억이나 검증된 선호가 아닙니다."
                   if is_u else "이전 방식의 1% Slow 작업별 실험 추첨입니다. 인간 행동 확률이 아닙니다."
                   if policy == "legacy_draw" else "Wonder 실행 정책 기록이 없습니다.")
    return {"policy": policy, "description": description, "draws": draws, "thoughts": thoughts,
            "responses": responses, "empty_responses": empty, "warnings": warnings,
            "probability_unit": "started_slow_task" if policy == "legacy_draw" else None}
