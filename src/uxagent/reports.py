"""Evidence-based, unreviewed improvement candidates and portable reports."""
from __future__ import annotations

import csv
import html
import io
import json
import os
import re

from .review import derive_issues


def redact(value):
    text = json.dumps(value, ensure_ascii=False)
    for name in ("OPENAI_API_KEY", "GEMINI_API_KEY", "TYPESAFE_API_KEY"):
        secret = os.environ.get(name)
        if secret:
            text = text.replace(json.dumps(secret)[1:-1], "[redacted]")
    text = re.sub(r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}", "[redacted]", text)
    return json.loads(text)


def build_cards(detail):
    steps = detail.get("steps", [])
    cards = derive_issues(steps)
    for card in cards:
        card["title"] = "반복 조작 또는 실행 오류 확인"
        card["observed_behavior"] = card.get("observed_behavior", "반복 행동이 기록됐습니다.")
        card["hypothesis"] = "화면 안내 또는 도구 동작의 문제일 수 있어 사람 검토가 필요합니다."
    checks = ((detail.get("summary") or {}).get("evaluator") or {}).get("feature_checks", [])
    for check in checks:
        if check.get("status") != "fail":
            continue
        cards.append({"issue_id":f"feature-{check['id']}","title":check["label"],
            "observed_behavior":f"종료 시 '{check['label']}' 확인 조건이 충족되지 않았습니다.",
            "hypothesis":"과업 미완료, 화면 정보 부족 또는 에이전트 조작 실패 가능성을 검토하세요.",
            "evidence_step_ids":[steps[-1]["step_id"]] if steps else [],
            "feature_evidence":check.get("evidence",{}),"review_status":"needs_human_review",
            "classification":"unmet_checkpoint"})
    for card in cards:
        card.update({"run_id":detail.get("run",{}).get("run_id"),
            "recommendation":"근거 화면과 행동을 재현해 원인을 구분하고, 필요한 안내·상태 표시·상호작용을 수정하세요.",
            "acceptance":"같은 과업·환경·확인 조건으로 재실행해 해당 조건 통과와 기존 조작의 회귀 여부를 확인하세요.",
            "severity":"사람 검토 필요", "source_location":"소스 연결 없음: 파일·라인 미확인"})
        card["evidence"] = [{"step_id":step.get("step_id"), "observation_id":step.get("observation_id"),
            "next_observation_id":step.get("next_observation_id")} for step in steps
            if step.get("step_id") in card.get("evidence_step_ids",[])]
    return redact(cards)


def export_report(detail, kind):
    safe = redact({"run":detail.get("run",{}),"config":detail.get("config",{}),
                   "summary":detail.get("summary"),"metrics":detail.get("metrics",{}),
                   "cards":detail.get("cards",build_cards(detail)),
                   "notice":"AI가 제안한 미검토 후보입니다. 실제 사용자 증언이나 확정된 사이트 결함이 아닙니다."})
    if kind == "json":
        return json.dumps(safe,ensure_ascii=False,indent=2)
    if kind == "csv":
        out=io.StringIO(newline="")
        writer=csv.writer(out)
        writer.writerow(["issue_id","title","review_status","observed_behavior","recommendation","acceptance","evidence_step_ids"])
        for card in safe["cards"]:
            values=[str(card.get(k,"")) for k in ("issue_id","title","review_status","observed_behavior","recommendation","acceptance","evidence_step_ids")]
            # Spreadsheet import must treat untrusted text as data, not a formula.
            writer.writerow(["'"+v if v.lstrip().startswith(("=","+","-","@")) else v for v in values])
        return out.getvalue()
    lines=[f"# Persona 결과: {safe['run'].get('run_id','')}", "", safe["notice"], "",
           f"과업: {safe['config'].get('task','')}", "", "## 결과", "",
           json.dumps(safe.get("summary"),ensure_ascii=False,indent=2)]
    if not safe["cards"]:
        lines.extend(["", "문제 후보가 없습니다. 사이트에 문제가 없다는 뜻은 아닙니다."])
    for card in safe["cards"]:
        lines.extend(["", f"## {card['issue_id']}: {card.get('title','')}", "",
            f"관찰: {card['observed_behavior']}", f"가설: {card['hypothesis']}",
            f"근거 단계: {card['evidence_step_ids']}", f"제안: {card['recommendation']}",
            f"완료 조건: {card['acceptance']}", "상태: 사람 검토 전"])
    text="\n".join(lines)+"\n"
    if kind == "md":
        return text
    if kind == "html":
        return '<!doctype html><html lang="ko"><meta charset="utf-8"><title>Persona 결과</title><style>body{max-width:960px;margin:32px auto;padding:24px;font:16px/1.7 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><body><pre>'+html.escape(text)+"</pre></body></html>"
    raise ValueError("지원 형식은 json, csv, md, html입니다")
