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
    for name in ("OPENAI_API_KEY", "GEMINI_API_KEY", "TYPESAFE_API_KEY", "ANTHROPIC_API_KEY"):
        secret = os.environ.get(name)
        if secret:
            text = text.replace(json.dumps(secret)[1:-1], "[redacted]")
    text = re.sub(r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}", "[redacted]", text)
    return json.loads(text)


def build_cards(detail):
    steps = detail.get("steps", [])
    scripted = detail.get("run",{}).get("execution_mode")=="scripted"
    cards = [] if scripted else derive_issues(steps)
    for card in cards:
        card["title"] = "반복 조작 또는 실행 오류 확인"
        card["observed_behavior"] = card.get("observed_behavior", "반복 행동이 기록됐습니다.")
        card["hypothesis"] = "화면 안내 또는 도구 동작의 문제일 수 있어 사람 검토가 필요합니다."
    checks = ((detail.get("summary") or {}).get("evaluator") or {}).get("feature_checks", [])
    for check in checks:
        if check.get("status") != "fail":
            continue
        cards.append({"issue_id":f"feature-{check['id']}","title":check["label"],
            "observed_behavior":f"{'점검 단계에서' if scripted else '종료 시'} '{check['label']}' 확인 조건이 충족되지 않았습니다.",
            "hypothesis":"과업 미완료, 화면 정보 부족 또는 에이전트 조작 실패 가능성을 검토하세요.",
            "evidence_step_ids":[check["step_id"]] if check.get("step_id") is not None else ([steps[-1]["step_id"]] if steps else []),
            "task_id":check.get("task_id"),"reason":check.get("reason"),
            "feature_evidence":check.get("evidence",{}),"review_status":"needs_human_review",
            "classification":"unmet_checkpoint"})
    if scripted:
        for step in steps:
            if step.get("error") or (step.get("result") or {}).get("error"):
                error=step.get("error") or step["result"]["error"]
                cards.append({"issue_id":f"action-{step['step_id']}","title":"조작 또는 관찰 오류 확인",
                    "observed_behavior":f"'{step.get('scenario_step','정의된 단계')}'에서 {error.get('code','unknown')} 오류가 기록됐습니다.",
                    "hypothesis":"선택자·화면 상태·도구 지원을 먼저 확인하세요. 사이트 사용성 문제로 확정할 수 없습니다.",
                    "evidence_step_ids":[step["step_id"]],"review_status":"needs_human_review","classification":"system_error_candidate"})
    guidance={
        "search":("검색 입력과 제출 후 목록 갱신, 검색어에 맞는 상품 표시를 확인하세요.","정의한 검색어로 재실행해 입력·URL·표시된 상품이 검색 조건에 맞는지 확인하세요."),
        "empty_search":("결과가 없을 때 안내와 검색어 수정 경로가 표시되도록 확인하세요.","없는 검색어에는 빈 결과 안내가 표시되고 검색어 변경 후 결과가 복원되는지 확인하세요."),
        "filters":("필터 적용 직후 가격·색상 선택 상태와 실제 상품 목록을 확인하세요. 필터 조건의 반영과 결과 갱신을 점검하세요.","정의된 가격·색상 조건에 맞는 상품만 표시되고 해제·초기화가 정상인지 재검증하세요."),
        "search_results":("사전 지정 검색 URL과 표시 상품명이 일치하는지 확인하세요. 검색 폼 제출은 별도 재검증이 필요합니다.","같은 검색 URL의 표시 결과를 재검증하고 폼 제출 결과와 구분하세요."),
        "filters_price":("선택한 가격 상한과 URL·화면에 표시된 상품 가격이 일치하는지 확인하세요.","같은 가격 상한으로 재실행해 표시된 상품이 상한을 넘지 않는지 확인하세요."),
        "reset_filters":("초기화 버튼이 선택 상태와 검색 결과를 함께 복원하는지 확인하세요.","필터를 적용한 뒤 초기화해 선택·적용 상태가 해제되고 원래 검색 결과 수가 복원되는지 확인하세요."),
        "detail":("상품 상세의 누락된 가격·사이즈·용도·재고·수령 안내를 확인하고 필요한 정보를 표시하세요.","같은 상품의 필수 정보와 가격·색상 조건이 실제 표시값으로 확인되는지 재검증하세요."),
        "detail_basic":("상세 상품명과 가격을 확인하세요. 추가 정보는 미검증 항목으로 구분하세요.","같은 상품 상세에서 이름·가격을 확인하고 미검증 필드까지 성공으로 처리하지 않는지 확인하세요.")}
    for card in cards:
        card.update({"run_id":detail.get("run",{}).get("run_id"),
            "recommendation":"근거 화면과 행동을 재현해 원인을 구분하고, 필요한 안내·상태 표시·상호작용을 수정하세요.",
            "acceptance":"같은 과업·환경·확인 조건으로 재실행해 해당 조건 통과와 기존 조작의 회귀 여부를 확인하세요.",
            "severity":"사람 검토 필요", "source_location":"소스 연결 없음: 파일·라인 미확인"})
        if card.get("task_id") in guidance:
            card["recommendation"],card["acceptance"]=guidance[card["task_id"]]
        card["evidence"] = [{"step_id":step.get("step_id"), "observation_id":step.get("observation_id"),
            "next_observation_id":step.get("next_observation_id")} for step in steps
            if step.get("step_id") in card.get("evidence_step_ids",[])]
    return redact(cards)


def export_report(detail, kind):
    safe = redact({"run":detail.get("run",{}),"config":detail.get("config",{}),
                   "summary":detail.get("summary"),"metrics":detail.get("metrics",{}),
                   "wonder":detail.get("wonder",{}),
                   "trace":detail.get("trace",[]),
                   "brain_stages":detail.get("brain_stages",[]),
                   "brain_tasks":detail.get("brain_tasks",[]),
                   "memories":detail.get("memories",[]),
                   "memory_changes":detail.get("memory_changes",[]),
                   "cards":detail.get("cards",build_cards(detail)),
                   "notice":("사전 정의한 브라우저 시나리오의 코드 평가 후보입니다. AI/페르소나 성능이나 확정 사이트 결함이 아닙니다." if detail.get("run",{}).get("execution_mode")=="scripted" else "AI가 제안한 미검토 후보입니다. 실제 사용자 증언이나 확정된 사이트 결함이 아닙니다.")})
    if kind == "json":
        return json.dumps(safe,ensure_ascii=False,indent=2)
    if kind == "csv":
        out=io.StringIO(newline="")
        writer=csv.writer(out)
        writer.writerow(["issue_id","title","review_status","observed_behavior","recommendation","acceptance","evidence_step_ids",
                         "record_type","record_id","stage_or_kind","status","text","observation_id","source_memory_ids","run_id"])
        def safe_cell(value):
            value = str(value if value is not None else "")
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
        for card in safe["cards"]:
            values=[str(card.get(k,"")) for k in ("issue_id","title","review_status","observed_behavior","recommendation","acceptance","evidence_step_ids")]
            # Spreadsheet import must treat untrusted text as data, not a formula.
            writer.writerow([safe_cell(v) for v in [*values, "card", "", "", "", "", "", "", safe["run"].get("run_id")]])
        for row in safe["brain_stages"]:
            writer.writerow([safe_cell(v) for v in ["", "", "", "", "", "", "", "brain_stage", row.get("record_id"),
                row.get("stage"), row.get("content_status", "generated"), row.get("text"), row.get("observation_id"),
                json.dumps(row.get("source_memory_ids") or [], ensure_ascii=False), safe["run"].get("run_id")]])
        for row in safe["brain_tasks"]:
            writer.writerow([safe_cell(v) for v in ["", "", "", "", "", "", "", "brain_task", row.get("task_id"),
                row.get("kind"), row.get("status"), row.get("reason_code"), row.get("observation_id"),
                json.dumps(row.get("source_memory_ids") or [], ensure_ascii=False), safe["run"].get("run_id")]])
        for row in safe["memories"]:
            writer.writerow([safe_cell(v) for v in ["", "", "", "", "", "", "", "memory", row.get("memory_id"),
                row.get("kind"), row.get("content_status"), row.get("text"),
                json.dumps(row.get("source_observation_ids") or [], ensure_ascii=False),
                json.dumps(row.get("source_memory_ids") or [], ensure_ascii=False), safe["run"].get("run_id")]])
        for row in safe["memory_changes"]:
            writer.writerow([safe_cell(v) for v in ["", "", "", "", "", "", "", "memory_change", row.get("memory_id"),
                row.get("change"), row.get("reason_code"), "", "", "", safe["run"].get("run_id")]])
        for row in safe["trace"]:
            outcome = {"proposal": row.get("action"), "execution": row.get("result"),
                       "next_observation_id": row.get("next_observation_id"), "evaluation": row.get("evaluation"),
                       "verification": row.get("verification", "unknown")}
            writer.writerow([safe_cell(v) for v in ["", "", "", "", "", "", "", "step", row.get("step_id"),
                "observation_action_evaluation", row.get("verification", "unknown"),
                json.dumps(outcome, ensure_ascii=False), row.get("observation_id"),
                json.dumps([memory.get("memory_id") for memory in row.get("memories", [])], ensure_ascii=False),
                safe["run"].get("run_id")]])
        return out.getvalue()
    source = (f"사전 정의 시나리오 ({safe['run'].get('source_kind') or '출처 미확인'})"
              if safe["run"].get("execution_mode") == "scripted" else "mock 모델 실행"
              if safe["run"].get("provider") == "mock" else
              f"설정 제공자 {safe['run'].get('provider') or '미확인'} (실제 호출은 모델 로그 확인)")
    lines=[f"# Persona 결과: {safe['run'].get('run_id','')}", "", safe["notice"], f"실행 출처: {source}", "",
           f"과업: {safe['config'].get('task','')}", "", "## 결과", "",
           json.dumps(safe.get("summary"),ensure_ascii=False,indent=2)]
    if safe["trace"]:
        lines.extend(["", "## 행동별 관찰·제안·실행·독립 평가", ""])
        for row in safe["trace"]:
            result = row.get("result") or {}
            execution = "실행됨" if result.get("ok") is True else "실패" if result.get("ok") is False else "미실행/미확인"
            lines.append(f"- 단계 {row.get('step_id','?')}: 관찰 {row.get('observation_id') or '없음'} → AI 제안 {json.dumps(row.get('action'), ensure_ascii=False)} → 도구 {execution} → 재관찰 {row.get('next_observation_id') or '없음'} → 독립 판정 {row.get('verification') or 'unknown'} ({(row.get('evaluation') or {}).get('reason') or '사유 미확인'})")
    if safe["brain_stages"] or safe["brain_tasks"]:
        lines.extend(["", "## 두 루프 생성·작업 기록", "",
                      "아래 단계는 AI 생성물이고, 작업 상태는 예약·완료·채택·실패·취소를 구분합니다. 과업 성공은 독립 평가를 확인하세요."])
        for row in safe["brain_stages"]:
            lines.append(f"- 생성 {row.get('stage','unknown')} [{row.get('record_id','')}], 관찰 {row.get('observation_id') or '없음'}, 기억 {row.get('source_memory_ids') or []}: {row.get('text','')}")
        for row in safe["brain_tasks"]:
            lines.append(f"- 작업 {row.get('kind','unknown')} [{row.get('task_id','')}]: {row.get('status','unknown')} ({row.get('reason_code') or '사유 없음'})")
    if safe["memories"]:
        removed = {row.get("memory_id") for row in safe["memory_changes"] if row.get("change") == "evicted"}
        lines.extend(["", "## 원본 기억 기록", "", "활성 목록에서 제거된 기억도 원본 기록으로 보존합니다."])
        for row in safe["memories"]:
            lines.append(f"- {row.get('memory_id','')} ({row.get('content_status','observed')}, {'활성 제거' if row.get('memory_id') in removed else '제거 기록 없음'}): {row.get('text','')}")
    thoughts=(safe.get("wonder") or {}).get("thoughts",[])
    if thoughts:
        lines.extend(["", "## AI가 생성한 가정된 생각", "",
                      "실제 사용자 기억이나 검증된 선호가 아닙니다. 1%는 실제 시작된 Slow 작업당 실험 추첨률이며 인간 행동 확률이 아닙니다."])
        lines.extend(f"- {thought.get('text','')} (기억 저장: {'예' if thought.get('stored') else '아니요'})"
                     for thought in thoughts)
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
