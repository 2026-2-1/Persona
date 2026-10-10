from __future__ import annotations

import asyncio, hashlib, json, os, socket, threading, time, uuid
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
from pydantic import ValidationError
from .schemas import StudyConfig, Persona
from .browser import BrowserSession
from .observation import observe
from .actions import ActionExecutor
from .evaluator import evaluate
from .llm import BudgetManager, MockProvider, OpenAIProvider, JevProvider, GeminiProvider, ClaudeProvider, CLAUDE_MODEL, GEMINI_MODEL, load_env_file, BudgetExceeded
from .fast_loop import FastLoop
from .memory import MemoryStore
from .slow_loop import SlowLoop
from .storage import write_json, JsonlWriter
from .security import normalize_origin


def load_study(path: str | Path):
    path=Path(path).resolve()
    raw=json.loads(path.read_text(encoding="utf-8"))
    config=StudyConfig.model_validate(raw)
    start_origin=normalize_origin(config.start_url)
    if start_origin not in config.allowed_origins:
        raise ValueError("start_url origin must be listed in allowed_origins")
    persona_path=Path(config.persona_file)
    if not persona_path.is_absolute():
        # Resolve config-relative first; support repository-root paths as fallback.
        beside=path.parent/persona_path
        persona_path=beside if beside.exists() else Path.cwd()/persona_path
    persona=Persona.model_validate_json(persona_path.read_text(encoding="utf-8"))
    return config,persona,path


class FixtureServer:
    def __init__(self, port=8000, host="127.0.0.1"): self.port=port; self.host=host; self.server=None; self.thread=None
    def start(self):
        try:
            with socket.create_connection(("127.0.0.1",self.port),timeout=.15): return False
        except OSError: pass
        fixture=Path(__file__).resolve().parents[2]/"tests"/"fixtures"
        handler=lambda *a,**kw:SimpleHTTPRequestHandler(*a,directory=str(fixture),**kw)
        self.server=ThreadingHTTPServer((self.host,self.port),handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        return True
    def close(self):
        if self.server:self.server.shutdown();self.server.server_close()


async def run_study(study_path, provider_name="mock", persona_override=None, headed=None, output_root="runs", *, persona_mode="persona", run_id_override=None):
    if persona_mode not in ("general", "persona"):
        raise ValueError("persona_mode must be general or persona")
    load_env_file(Path(study_path).resolve().parent / ".env")
    load_env_file()
    config,persona,config_path=load_study(study_path)
    if persona_override is not None: persona=persona_override
    run_id=run_id_override or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
    if not isinstance(run_id,str) or not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
        raise ValueError("run_id_override must be a safe identifier")
    is_fixture=urlsplit(config.start_url).path.endswith("shop.html") and urlsplit(config.start_url).hostname in ("localhost","127.0.0.1")
    server=FixtureServer(urlsplit(config.start_url).port or (443 if urlsplit(config.start_url).scheme=="https" else 80)) if is_fixture else None
    server_started=server.start() if server else False
    run_dir=Path(output_root)/run_id;run_dir.mkdir(parents=True,exist_ok=False)
    now=datetime.now(timezone.utc).isoformat()
    write_json(run_dir/"config.json",config.model_dump());write_json(run_dir/"persona.json",persona.model_dump() if persona_mode=="persona" else {"constraints":persona.constraints,"intent":persona.intent,"condition":"general"})
    write_json(run_dir/"run.json",{"run_id":run_id,"started_at":now,"study_id":config.study_id,"provider":provider_name,"model":config.model if provider_name=="live" else CLAUDE_MODEL if provider_name=="claude" else GEMINI_MODEL if provider_name in ("jev","gemini") else "mock-v1","prompt_version":"fast-2","condition":persona_mode})
    steps=JsonlWriter(run_dir/"steps.jsonl");calls=JsonlWriter(run_dir/"llm_calls.jsonl");memory_writer=JsonlWriter(run_dir/"memory.jsonl")
    started=time.monotonic();termination="browser_error";verification="unknown";error_counts={};action_attempts=action_successes=step_count=back_count=0;previous_error=None;step_history=[];seen={};last_obs=None;slow=None
    budget=BudgetManager(config.max_llm_requests,config.max_total_tokens)
    llm_elapsed_total=0
    def log_call(record):
        nonlocal llm_elapsed_total
        llm_elapsed_total+=int(record.get("elapsed_ms",0) or 0)
        if "provider" not in record:
            record["provider"]="gemini" if str(record.get("model","")).startswith("gemini-") else "typesafe" if str(record.get("model","")).startswith("jev-") else "mock" if record.get("model")=="mock-v1" else "claude" if str(record.get("model","")).startswith("claude-") else "openai"
        if "estimated_cost_usd" not in record:
            from .llm import estimate_cost_usd
            record["estimated_cost_usd"]=estimate_cost_usd(record["provider"],record.get("input_tokens"),record.get("output_tokens"))
        record.setdefault("fallback_reason",None)
        calls.write(record)
    provider=MockProvider() if provider_name=="mock" else JevProvider() if provider_name=="jev" else OpenAIProvider() if provider_name=="live" else ClaudeProvider() if provider_name=="claude" else GeminiProvider()
    model=config.model if provider_name=="live" else CLAUDE_MODEL if provider_name=="claude" else GEMINI_MODEL if provider_name in ("jev","gemini") else "mock-v1"
    memory=MemoryStore(run_id,memory_writer)
    fast=FastLoop(provider,budget,model,config.temperature,config.max_output_tokens,log_call)
    actual_headed=config.headed if headed is None else headed
    try:
        async with BrowserSession(actual_headed,config.viewport.width,config.viewport.height) as browser:
            executor=ActionExecutor(browser,config.allowed_origins,config.action_timeout_ms,config.settle_timeout_ms,allow_scroll=config.explicit_scroll)
            await browser.set_allowed_origins(config.allowed_origins)
            page=browser.active
            await page.goto(config.start_url,wait_until="domcontentloaded",timeout=config.action_timeout_ms)
            if not is_fixture:
                try:
                    await page.wait_for_function("document.body && document.body.innerText.trim().length > 500",
                                                 timeout=min(6000,config.action_timeout_ms))
                except Exception:
                    pass
            run_deadline=started+config.run_timeout_seconds
            for _ in range(config.max_steps):
                if time.monotonic()>=run_deadline:termination="run_timeout";break
                observation,registry=await observe(browser,run_dir,config.max_observation_text,config.max_observation_elements,previous_error)
                pre_observed_at=datetime.now(timezone.utc).isoformat()
                last_obs=observation
                executor.publish(registry)
                evaluation=await evaluate(browser.active,config.evaluator_id,getattr(config,"evaluation_checks",None))
                verification=evaluation["verification"]
                if verification=="success":termination="verified_success";break
                try:
                    if config.embedding_model:
                        memories=await memory.retrieve_with_embeddings(config.task+" "+observation.html[:1500],config.memory_limit,provider,budget,config.embedding_model,log_call)
                    else:
                        memories=list(memory.retrieve(config.task,config.memory_limit))
                except BudgetExceeded:
                    termination="budget_exceeded";break
                except Exception as exc:
                    memories=list(memory.retrieve(config.task,config.memory_limit))
                    previous_error={"code":"embedding_error","message":str(exc)[:300]}
                # Mock model uses the action history deterministically; the live prompt sees only bounded logged context.
                history_tail=step_history[-config.recent_step_count:] if config.recent_step_count else []
                memories.extend({"action_type":h["mock_stage"],"text":h["summary"]} for h in history_tail)
                step_id=step_count+1
                try:
                    decision_started=time.monotonic()
                    remaining=run_deadline-time.monotonic()
                    if remaining<=0:termination="run_timeout";break
                    async with asyncio.timeout(remaining):
                        decision=await fast.decide(persona,config.task,observation,memories,previous_error,config.max_steps-step_count,persona_mode=persona_mode)
                    decision_ms=int((time.monotonic()-decision_started)*1000)
                except BudgetExceeded:
                    termination="budget_exceeded";break
                except TimeoutError:
                    termination="run_timeout";break
                except Exception as exc:
                    step_count+=1
                    termination="model_error";previous_error={"code":"model_output_error","message":str(exc)[:400]}
                    steps.write({"step_id":step_id,"observation_id":observation.observation_id,"decision":None,"action":None,"result":None,"error":previous_error,"verification":verification})
                    error_counts[previous_error["code"]]=error_counts.get(previous_error["code"],0)+1;break
                step_count+=1
                if decision.action is None:
                    steps.write({"step_id":step_id,"observation_id":observation.observation_id,"decision":decision.model_dump(),"action":None,"result":None,"next_observation_id":observation.observation_id,"memory_ids":[m["memory_id"] for m in memories if "memory_id" in m],"verification":verification,"timing_ms":{"llm":decision_ms}})
                    termination="agent_finished" if decision.finish.claim=="completed" else "agent_gave_up"
                    memory.append("plan",decision.plan,[step_id],[observation.observation_id],"generated")
                    break
                action_attempts+=1
                if decision.action.type=="back": back_count+=1
                action_result=await executor.execute(decision.action)
                if action_result.ok:action_successes+=1
                if action_result.error:
                    previous_error=action_result.error;code=previous_error["code"];error_counts[code]=error_counts.get(code,0)+1
                else:previous_error=None
                try:
                    next_obs,next_registry=await observe(browser,run_dir,config.max_observation_text,config.max_observation_elements,previous_error)
                except Exception:
                    steps.write({"step_id":step_id,"observation_id":observation.observation_id,"decision_id":decision.decision_id,"action_id":action_result.action_id,"next_observation_id":None,"pre_observed_at":pre_observed_at,"post_observed_at":None,"recorded_at":datetime.now(timezone.utc).isoformat(),"decision":decision.model_dump(),"action":decision.action.model_dump(),"result":action_result.model_dump(),"verification":verification,"error":{"code":"post_observation_error","message":"Post-action observation could not be captured."},"timing_ms":{"llm":decision_ms,"action":action_result.elapsed_ms}})
                    raise
                post_observed_at=datetime.now(timezone.utc).isoformat()
                executor.publish(next_registry)
                post_eval=await evaluate(browser.active,config.evaluator_id,getattr(config,"evaluation_checks",None));verification=post_eval["verification"];evaluation=post_eval
                fingerprint_state=next_obs.model_dump(exclude={"observation_id","capture","error","tabs"})
                fingerprint=hashlib.sha256(json.dumps(fingerprint_state,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                action_key=json.dumps({k:getattr(decision.action,k) for k in ("type","target_id","text","option_value","url","target_tab_id") if getattr(decision.action,k) is not None},sort_keys=True,ensure_ascii=False)
                repeated_key=fingerprint+action_key;seen[repeated_key]=seen.get(repeated_key,0)+1
                if seen[repeated_key]>=config.repeated_state_action_limit:termination="stuck"
                summary=f"{decision.action.type} {decision.action.target_id or decision.action.url or ''}: {'ok' if action_result.ok else action_result.error['code']}"
                memory.append("observation",observation.html[:600],[step_id],[observation.observation_id])
                memory.append("plan",decision.plan,[step_id],[observation.observation_id],"generated")
                memory.append("action",summary,[step_id],[observation.observation_id],"observed")
                mock_stage={"type":"type","click":"click-search","select":"select-color" if decision.action.option_value=="검정" else "select-price" if decision.action.option_value=="30000" else "apply-filter"}.get(decision.action.type,decision.action.type)
                # use semantic target to distinguish repeated select/click phases
                if decision.action.type=="click" and decision.action.target_id and "필터" in decision.action.target_id:mock_stage="apply-filter"
                step_history.append({"mock_stage":mock_stage,"summary":summary})
                steps.write({"step_id":step_id,"observation_id":observation.observation_id,"decision_id":decision.decision_id,"action_id":action_result.action_id,"next_observation_id":next_obs.observation_id,"pre_observed_at":pre_observed_at,"post_observed_at":post_observed_at,"recorded_at":datetime.now(timezone.utc).isoformat(),"decision":decision.model_dump(),"action":decision.action.model_dump(),"result":action_result.model_dump(),"memory_ids":[m["memory_id"] for m in memories if "memory_id" in m],"verification":verification,"timing_ms":{"llm":decision_ms,"action":action_result.elapsed_ms,"observation":0,"settle":0}})
                if config.enable_slow_loop:
                    if slow is None:slow=SlowLoop(provider,budget,model,config.temperature,config.max_output_tokens,memory,log_call)
                    if action_attempts%config.reflection_every_actions==0 or action_result.error:
                        slow.schedule(persona,config.task,previous_error,config.enable_wonder)
                if termination=="stuck":break
                if verification=="success":termination="verified_success";break
            else:termination="max_steps"
    except KeyboardInterrupt:
        termination="interrupted"
    except Exception as exc:
        termination="browser_error";previous_error={"code":"browser_error","message":str(exc)[:500]}
        error_counts["browser_error"]=error_counts.get("browser_error",0)+1
    finally:
        if slow: await slow.close()
        if server and server_started:server.close()
    elapsed=int((time.monotonic()-started)*1000)
    if termination=="verified_success":verification="success"
    elif verification=="failure":verification="failure"
    call_records=[json.loads(line) for line in (run_dir/"llm_calls.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    provider_usage={}
    for record in call_records:
        entry=provider_usage.setdefault(record.get("provider","unknown"),{"requests":0,"input_tokens":0,"output_tokens":0,"estimated_cost_usd":0.0,"cost_known":True})
        entry["requests"]+=1
        if record.get("input_tokens") is None or record.get("output_tokens") is None: entry["cost_known"]=False
        else:
            entry["input_tokens"]+=record["input_tokens"];entry["output_tokens"]+=record["output_tokens"]
        if record.get("estimated_cost_usd") is None: entry["cost_known"]=False
        else: entry["estimated_cost_usd"]+=record["estimated_cost_usd"]
    for entry in provider_usage.values():
        if not entry["cost_known"]: entry["estimated_cost_usd"]=None
        del entry["cost_known"]
    summary={"run_id":run_id,"termination_reason":termination,"verification":verification,"evaluator":evaluation if 'evaluation' in locals() else {"verification":"unknown"},
             "steps":step_count,"action_attempts":action_attempts,"action_successes":action_successes,"llm_request_count":budget.requests,
             "llm_tokens":budget.tokens,"cost":sum((entry["estimated_cost_usd"] or 0) for entry in provider_usage.values()) if all(entry["estimated_cost_usd"] is not None for entry in provider_usage.values()) else None,
             "provider_usage":provider_usage,"elapsed_ms":elapsed,"llm_ms":llm_elapsed_total,"back_count":back_count,"error_counts":error_counts,"last_error":previous_error,
             "provider":provider_name,"model":model,"condition":persona_mode,"slow_loop_status":slow.status if slow else ("idle" if config.enable_slow_loop else "disabled"),"started_at":now,"finished_at":datetime.now(timezone.utc).isoformat(),"last_observation_id":last_obs.observation_id if last_obs else None}
    from .metrics import run_metrics
    step_records=[json.loads(line) for line in (run_dir/"steps.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    summary["metrics"]=run_metrics(run_dir,step_records,attempted_count=action_attempts)
    write_json(run_dir/"summary.json",summary)
    steps.close();calls.close();memory_writer.close()
    return run_dir,summary
