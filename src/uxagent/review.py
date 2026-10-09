from __future__ import annotations

import html, json, re
from collections import Counter
from pathlib import Path
from .storage import JsonlWriter


QUESTIONS=["과제를 완료했다고 생각하나요? 판단에 사용한 화면은 무엇인가요?","진행 중 이해하기 어려웠던 부분은 무엇인가요?","다시 이용한다면 바뀌었으면 하는 부분은 무엇인가요?"]


def read_jsonl(path):
    if not path.exists():return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def derive_issues(steps):
    actions=Counter();errors=Counter();sources={}
    for s in steps:
        a=s.get("action") or {};key=(a.get("type"),a.get("target_id"))
        if a: actions[key]+=1
        if (s.get("result") or {}).get("error"):
            code=s["result"]["error"].get("code","unknown");errors[code]+=1;sources.setdefault(code,[]).append(s["step_id"])
    issues=[]
    for (kind,target),n in actions.items():
        if n>=3:issues.append({"issue_id":f"issue-{len(issues)+1:02d}","hypothesis":"The same control may be difficult to use or its state may be unclear.","evidence_step_ids":[s["step_id"] for s in steps if ((s.get("action") or {}).get("type"),(s.get("action") or {}).get("target_id"))==(kind,target)],"observed_behavior":f"Repeated {kind} action on {target}.","alternative_explanations":["observation extraction missed a state change","model misread the current page"],"review_status":"needs_human_review"})
    for code,n in errors.items():
        if code not in ("action_timeout","navigation_blocked") and n>=2:
            issues.append({"issue_id":f"issue-{len(issues)+1:02d}","hypothesis":"Repeated interaction errors may indicate a usability issue.","evidence_step_ids":sources[code],"observed_behavior":f"Repeated system interaction error: {code}.","alternative_explanations":["browser or network instability","unsupported control behavior"],"review_status":"needs_human_review","classification":"system_error_candidate"})
    return issues


def create_review(run_dir):
    run=Path(run_dir).resolve();summary=json.loads((run/"summary.json").read_text());config=json.loads((run/"config.json").read_text());persona=json.loads((run/"persona.json").read_text());steps=read_jsonl(run/"steps.jsonl");calls=read_jsonl(run/"llm_calls.jsonl");memories=read_jsonl(run/"memory.jsonl")
    issues=derive_issues(steps);(run/"issues.json").write_text(json.dumps(issues,ensure_ascii=False,indent=2),encoding="utf-8")
    parts=[]
    for s in steps:
        pre=(s.get("observation_id") or "");nxt=s.get("next_observation_id") or pre
        reflections=[m for m in memories if m.get("kind") in ("reflection","wonder") and s.get("step_id") in m.get("source_step_ids",[])]
        imgs=[]
        for obs in dict.fromkeys([pre,nxt]):
            p=run/"observations"/f"{obs}.png"
            if p.exists():imgs.append(f'<a href="observations/{html.escape(obs)}.png"><img loading="lazy" alt="{html.escape(obs)}" src="observations/{html.escape(obs)}.png"></a><a href="observations/{html.escape(obs)}.json">observation JSON</a>')
        parts.append(f"<article><h3>Step {s.get('step_id')}</h3><p><b>Decision</b> {html.escape(str(s.get('decision') or ''))}</p><p><b>Action</b> {html.escape(str(s.get('action') or 'finish'))}</p><p><b>Result</b> {html.escape(str(s.get('result') or s.get('error') or ''))}</p><p><b>Verification</b> {html.escape(str(s.get('verification')))}</p><p><b>Reflection</b> {html.escape(json.dumps(reflections,ensure_ascii=False))}</p><div class='images'>{''.join(imgs)}</div></article>")
    header=f"<h1>UXAgent run {html.escape(summary['run_id'])}</h1><p>Termination: {html.escape(summary['termination_reason'])} · Verification: {html.escape(summary['verification'])}</p><pre>{html.escape(json.dumps({'config':config,'persona':persona,'summary':summary,'llm_calls':calls},ensure_ascii=False,indent=2))}</pre>"
    body="".join(parts)+"<h2>Issue candidates</h2><pre>"+html.escape(json.dumps(issues,ensure_ascii=False,indent=2))+"</pre>"
    document="<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>UXAgent review</title><style>body{font:15px system-ui;max-width:1100px;margin:2rem auto;color:#202124}article{border:1px solid #ddd;padding:1rem;margin:1rem 0;border-radius:8px}.images{display:flex;gap:1rem}.images img{width:min(45vw,480px);border:1px solid #bbb}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f5f5;padding:1rem}</style>"+header+body
    (run/"review.html").write_text(document,encoding="utf-8")
    return run/"review.html",issues


def create_survey(run_dir):
    run=Path(run_dir).resolve();summary=json.loads((run/"summary.json").read_text());steps=read_jsonl(run/"steps.jsonl")
    evidence=[s["step_id"] for s in steps if s.get("observation_id")]
    success=summary.get("verification")=="success"
    answers=[{"question_id":"q1","answer":("기록에서는 과제가 완료된 것으로 확인되었습니다." if success else "기록에서는 성공이 확인되지 않았습니다.")+ (f" 근거 화면은 step {evidence[-1]}입니다." if evidence else " 기록에서 판단 근거를 확인할 수 없습니다."),"source_step_ids":evidence[-1:] if evidence else [],"data_type":"simulated_self_report"},
             {"question_id":"q2","answer":"기록에서 반복 오류나 반복 행동이 확인되지 않았습니다." if not derive_issues(steps) else "반복 행동 또는 오류가 기록되어 있어 해당 화면을 검토할 수 있습니다.","source_step_ids":[i for x in derive_issues(steps) for i in x["evidence_step_ids"]],"data_type":"simulated_self_report"},
             {"question_id":"q3","answer":"기록만으로 실제 사용자의 개선 요구를 확인할 수 없습니다.","source_step_ids":[],"data_type":"simulated_self_report"}]
    payload=[{"question":q,"response":a} for q,a in zip(QUESTIONS,answers)]
    (run/"survey.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8");return payload


def interview(run_dir, at_step: int, question: str):
    run=Path(run_dir).resolve();steps=read_jsonl(run/"steps.jsonl");eligible=[s for s in steps if s.get("step_id",0)<=at_step]
    if not eligible or at_step<1:raise ValueError("at-step must identify an existing recorded step")
    relevant=[s["step_id"] for s in eligible if s.get("observation_id")]
    persona=json.loads((run/"persona.json").read_text(encoding="utf-8"));config=json.loads((run/"config.json").read_text(encoding="utf-8"))
    available={m["memory_id"]:m for m in read_jsonl(run/"memory.jsonl") if any(m["memory_id"] in s.get("memory_ids",[]) for s in eligible)}
    last=eligible[-1]
    snapshot_id=last.get("next_observation_id") if last.get("action") else last.get("observation_id")
    snapshot_path=run/"observations"/f"{snapshot_id}.json" if snapshot_id else None
    snapshot=json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path and snapshot_path.exists() else None
    visible_text=[]
    if snapshot:
        visible_text=[e["name"] for group in ("clickable_elements","input_elements","select_elements") for e in snapshot.get(group,[])]
    last=eligible[-1];action=last.get("action") or {};decision=last.get("decision") or {}
    observed_summary=", ".join(visible_text[:8]) if visible_text else "화면 요소가 기록되지 않았습니다"
    answer=(f"현재 과제는 ‘{config.get('task','')}’였고, persona의 의도는 ‘{persona.get('intent','')}’였습니다. "
            f"이 시점의 최근 계획은 ‘{decision.get('plan','기록 없음')}’이며, 최근 행동은 ‘{action.get('type','종료 제안')}’입니다. "
            f"기록된 현재 화면에는 {observed_summary}가 표시되어 있습니다. 이 기록은 화면에서 확인 가능한 행동만 보여 주므로, 실제로 무엇을 생각하거나 느꼈는지는 확인할 수 없습니다.")
    entry={"at_step":at_step,"question":question,"answer":answer,"source_step_ids":relevant,"memory_ids":list(available),"observation_id":snapshot_id,"visible_element_names":visible_text,"uncertainty":"high","data_type":"simulated_interview"}
    with (run/"interviews.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps(entry,ensure_ascii=False)+"\n")
    return entry
