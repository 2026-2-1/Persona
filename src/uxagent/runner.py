from __future__ import annotations

import asyncio, hashlib, json, os, secrets, socket, threading, time, uuid
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
from pydantic import ValidationError
from .schemas import BrainStageRecord, StudyConfig, Persona
from .browser import BrowserSession
from .observation import observe
from .actions import ActionExecutor
from .evaluator import evaluate
from .llm import BudgetManager, MockProvider, OpenAIProvider, JevProvider, GeminiProvider, ClaudeProvider, CLAUDE_MODEL, GEMINI_MODEL, load_env_file, BudgetExceeded, provider_for_model
from .fast_loop import FastLoop
from .brain import Brain
from .memory import MemoryStore
from .slow_loop import SlowLoop
from .storage import write_json, JsonlWriter
from .security import normalize_origin
from .model_catalog import resolve_model


def measured_usage(records, requests):
    """Measured call subtotals; completeness also requires every reserved request logged."""
    from .metrics import _count, _number
    usage = {}
    for record in records:
        entry = usage.setdefault(record.get('provider', 'unknown'), {'requests': 0})
        entry['requests'] += 1
    for provider, entry in usage.items():
        calls = [r for r in records if r.get('provider', 'unknown') == provider]
        entry['requests_complete'] = len(records) == requests
        entry['requests_measured_total'] = len(calls)
        costs = [r['estimated_cost_usd'] for r in calls if _number(r.get('estimated_cost_usd'))]
        entry['estimated_cost_usd_complete'] = len(costs) == len(calls) and len(records) == requests
        entry['estimated_cost_usd_measured_total'] = sum(costs) if costs else None
        for key in ('input_tokens', 'output_tokens'):
            known = [r[key] for r in calls if _count(r.get(key))]
            entry[key + '_measured_total'] = sum(known) if known else None
            entry[key + '_known_calls'] = len(known)
            entry[key + '_unknown_calls'] = len(calls) - len(known)
            entry[key + '_complete'] = len(known) == len(calls) and len(records) == requests
    totals = [r['input_tokens'] + r['output_tokens'] for r in records
              if _count(r.get('input_tokens')) and _count(r.get('output_tokens'))]
    costs = [r['estimated_cost_usd'] for r in records if _number(r.get('estimated_cost_usd'))]
    return {'provider_usage': usage, 'provider_usage_complete': len(records) == requests,
            'cost_complete': len(costs) == len(records) == requests,
            'cost_measured_total': sum(costs) if costs else (0 if requests == 0 else None),
            'llm_tokens_complete': len(totals) == len(records) == requests,
            'llm_tokens_measured_total': sum(totals) if totals else (0 if requests == 0 else None),
            'llm_tokens_known_calls': len(totals),
            'llm_tokens_unknown_calls': max(requests, len(records)) - len(totals)}


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


def model_routes(provider_name: str, model: str):
    generator = "gemini" if provider_name == "jev" else "openai" if provider_name == "live" else provider_for_model(model, provider_name)
    routes = {stage: {"provider": generator, "model": model} for stage in
              ("perception", "plan", "decision", "importance", "reflection", "plan_review", "wonder")}
    if provider_name == "jev":
        routes["decision"] = {"provider": "typesafe", "model": "jev-latest"}
        routes["decision_choice"] = routes["decision"]
        routes["decision_fallback"] = {"provider": "gemini", "model": model}
    return routes


def validate_provider_configuration(provider_name: str, config: StudyConfig):
    if provider_name == "jev":
        if not os.environ.get("TYPESAFE_API_KEY"):
            raise ValueError("Jev requires a TypeSafe API key before execution")
        if not os.environ.get("GEMINI_API_KEY"):
            raise ValueError("Jev requires a Gemini API key for every generation stage")
    if config.embedding_model and provider_name not in {"mock", "live"}:
        raise ValueError("This provider does not support the configured embedding model")


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


async def run_study(study_path, provider_name="mock", persona_override=None, headed=None, output_root="runs", *, persona_mode="persona", run_id_override=None, stop_file=None):
    if persona_mode not in ("general", "persona"):
        raise ValueError("persona_mode must be general or persona")
    load_env_file(Path(study_path).resolve().parent / ".env")
    load_env_file()
    config,persona,config_path=load_study(study_path)
    model = resolve_model(provider_name, config.provider_model) if config.provider_model is not None else config.model if provider_name == "live" else resolve_model(provider_name)
    validate_provider_configuration(provider_name, config)
    routes = model_routes(provider_name, model)
    if persona_override is not None: persona=persona_override
    run_id=run_id_override or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
    if not isinstance(run_id,str) or not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
        raise ValueError("run_id_override must be a safe identifier")
    is_fixture=urlsplit(config.start_url).path.endswith("shop.html") and urlsplit(config.start_url).hostname in ("localhost","127.0.0.1")
    server=FixtureServer(urlsplit(config.start_url).port or (443 if urlsplit(config.start_url).scheme=="https" else 80)) if is_fixture else None
    server_started=server.start() if server else False
    run_dir=Path(output_root)/run_id;run_dir.mkdir(parents=True,exist_ok=False)
    now=datetime.now(timezone.utc).isoformat()
    wonder_seed=config.wonder_seed if config.wonder_seed is not None else secrets.randbits(63)
    write_json(run_dir/"config.json",config.model_dump());write_json(run_dir/"persona.json",persona.model_dump() if persona_mode=="persona" else {"constraints":persona.constraints,"intent":persona.intent,"condition":"general"})
    write_json(run_dir/"run.json",{"run_id":run_id,"started_at":now,"study_id":config.study_id,"provider":provider_name,"model":model,"model_routes":routes,"prompt_version":"brain-3","condition":persona_mode,"wonder_seed":wonder_seed if config.enable_wonder else None,
        "execution_mode":"ai", "source_kind":"synthetic_fixture" if is_fixture else config.source_kind})
    steps=JsonlWriter(run_dir/"steps.jsonl");calls=JsonlWriter(run_dir/"llm_calls.jsonl");memory_writer=JsonlWriter(run_dir/"memory.jsonl");memory_change_writer=JsonlWriter(run_dir/"memory_changes.jsonl")
    brain_task_writer=JsonlWriter(run_dir/"brain_tasks.jsonl");brain_stage_writer=JsonlWriter(run_dir/"brain_stages.jsonl");wonder_draw_writer=JsonlWriter(run_dir/"wonder_draws.jsonl")
    started=time.monotonic();termination="browser_error";verification="unknown";error_counts={};action_attempts=action_successes=step_count=back_count=0;previous_error=None;step_history=[];seen={};last_obs=None;slow=None;brain=None
    budget=BudgetManager(config.max_llm_requests,config.max_total_tokens)
    llm_elapsed_total=0
    def log_call(record):
        nonlocal llm_elapsed_total
        llm_elapsed_total+=int(record.get("elapsed_ms",0) or 0)
        if "provider" not in record:
            record["provider"]=provider_for_model(record.get("model"))
        if "estimated_cost_usd" not in record:
            from .llm import estimate_cost_usd
            record["estimated_cost_usd"]=estimate_cost_usd(record["provider"],record.get("input_tokens"),record.get("output_tokens"),model=record.get("model"))
        record.setdefault("fallback_reason",None)
        calls.write(record)
    def write_fast_stage(stage, observation, text, source_memory_ids, *, plan_id=None, task_id=None,
                         action=None, finish=None):
        record_id=f"stage-{stage}-{uuid.uuid4().hex}"
        record=BrainStageRecord(record_id=record_id,task_id=task_id,run_id=run_id,stage=stage,
            observation_id=observation.observation_id,
            plan_id=plan_id,plan_version=1 if plan_id else None,
            source_memory_ids=source_memory_ids,text=text,action=action,finish=finish,
            recorded_at=datetime.now(timezone.utc))
        brain_stage_writer.write(record.model_dump())
        return record
    def with_boundary_memories(retrieved, adopted, limit):
        selected=[];seen=set()
        for entry in [*reversed(adopted),*retrieved]:
            memory_id=entry.get("memory_id")
            if memory_id in seen:continue
            selected.append(entry);seen.add(memory_id)
            if len(selected)>=limit:break
        return selected
    async def evaluate_current(page):
        try:
            return await evaluate(page,config.evaluator_id,getattr(config,"evaluation_checks",None))
        except Exception:
            return {"verification":"unknown","reason":"evaluator_error","feature_checks":[]}
    def write_unexecuted_step(step_id, observation, observed_at, code, message, *, decision=None, memory_ids=None):
        steps.write({"step_id":step_id,"observation_id":observation.observation_id,
                     "decision":decision.model_dump() if decision is not None else None,
                     "action":None,"result":None,"next_observation_id":None,
                     "pre_observed_at":observed_at,"post_observed_at":None,
                     "recorded_at":datetime.now(timezone.utc).isoformat(),
                     "memory_ids":memory_ids or [],"verification":"unknown",
                     "evaluation":{"verification":"unknown","reason":"not_evaluated","feature_checks":[]},
                     "error":{"code":code,"message":message,
                              **({"budget_reason":budget.last_exceeded_reason} if code=="budget_exceeded" else {})}})
    def stop_requested():
        return stop_file is not None and Path(stop_file).is_file()
    provider=MockProvider() if provider_name=="mock" else JevProvider() if provider_name=="jev" else OpenAIProvider() if provider_name=="live" else ClaudeProvider() if provider_name=="claude" else GeminiProvider()
    memory=MemoryStore(run_id,memory_writer,max_active_memories=config.max_active_memories,change_writer=memory_change_writer)
    fast=FastLoop(provider,budget,model,config.temperature,config.max_output_tokens,log_call)
    slow=SlowLoop(provider,budget,model,config.temperature,config.max_output_tokens,
                  memory,brain_task_writer,brain_stage_writer,log_call,defer_adoption=True,
                  wonder_enabled=config.enable_wonder,wonder_seed=wonder_seed,
                  wonder_draw_writer=wonder_draw_writer,importance_enabled=True)
    brain=Brain(fast,slow,memory,persona,persona_mode,brain_task_writer)
    evaluation={"verification":"unknown","reason":"not_evaluated","feature_checks":[]}
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
                if stop_requested():termination="cancelled";break
                if time.monotonic()>=run_deadline:termination="run_timeout";break
                observation,registry=await observe(browser,run_dir,config.max_observation_text,config.max_observation_elements,previous_error)
                pre_observed_at=datetime.now(timezone.utc).isoformat()
                last_obs=observation
                executor.publish(registry)
                evaluation={"verification":"unknown","reason":"not_evaluated","feature_checks":[]}
                verification="unknown"
                step_id=step_count+1
                if stop_requested():
                    step_count+=1
                    write_unexecuted_step(step_id,observation,pre_observed_at,
                        "cancelled","Run was stopped after observation.")
                    termination="cancelled";break
                observation_memory=memory.append("observation",observation.html[:600],
                    [step_id],[observation.observation_id])
                perception_boundary=brain.begin_stage("perception",observation.observation_id)
                try:
                    if config.embedding_model:
                        memories=await memory.retrieve_with_embeddings(config.task+" "+observation.html[:1500],config.memory_limit,provider,budget,config.embedding_model,log_call)
                    else:
                        memories=list(memory.retrieve(config.task,config.memory_limit))
                except BudgetExceeded:
                    step_count+=1
                    write_unexecuted_step(step_id,observation,pre_observed_at,
                        "budget_exceeded","Model request budget was exhausted.")
                    termination="budget_exceeded";break
                except Exception as exc:
                    memories=list(memory.retrieve(config.task,config.memory_limit))
                    previous_error={"code":"embedding_error","message":str(exc)[:300]}
                # Keep scored memories and recent actions separate so history cannot displace top-ranked memories.
                memories=with_boundary_memories(memories,perception_boundary,
                    4 if hasattr(provider,"choose") else 6)
                history_tail=step_history[-config.recent_step_count:] if config.recent_step_count else []
                recent_actions=[{"action_type":h["mock_stage"],"text":h["summary"]} for h in history_tail]
                try:
                    decision_started=time.monotonic()
                    remaining=run_deadline-time.monotonic()
                    if remaining<=0:
                        step_count+=1
                        write_unexecuted_step(step_id,observation,pre_observed_at,
                            "run_timeout","Run deadline was reached before a model decision.")
                        termination="run_timeout";break
                    async with asyncio.timeout(remaining):
                        perception=await brain.perceive(config.task,observation,memories)
                        perception_sources=[m["memory_id"] for m in memories if "memory_id" in m]
                        perception_task_id=brain.fast_task_id("perception")
                        perception_record=write_fast_stage("perception",observation,perception,
                            perception_sources,task_id=perception_task_id)
                        brain.complete_fast("perception",perception_record)
                        perception_memory=memory.append("observation",perception,[step_id],
                            [observation.observation_id],"generated",source_memory_ids=perception_sources,
                            source_stage_record_id=perception_record.record_id)
                        brain.schedule_reflection(config.task,observation.observation_id,
                                                  error=previous_error)
                        plan_boundary=brain.begin_stage("plan",observation.observation_id)
                        if config.embedding_model:
                            plan_memories=await memory.retrieve_with_embeddings(config.task+" "+observation.html[:1500],config.memory_limit,provider,budget,config.embedding_model,log_call)
                        else:
                            plan_memories=list(memory.retrieve(config.task,config.memory_limit))
                        plan_memories=with_boundary_memories(plan_memories,plan_boundary,
                            4 if hasattr(provider,"choose") else 6)
                        plan=await brain.plan(config.task,observation,plan_memories,perception,
                            previous_error,recent_actions,config.max_steps-step_count)
                        plan_sources=[m["memory_id"] for m in plan_memories if "memory_id" in m]
                        plan_task_id=brain.fast_task_id("plan")
                        plan_record=write_fast_stage("plan",observation,plan,plan_sources,
                            plan_id=f"plan-{uuid.uuid4().hex}",task_id=plan_task_id)
                        brain.complete_fast("plan",plan_record)
                        plan_memory=memory.append("plan",plan,[step_id],[observation.observation_id],
                            "generated",source_memory_ids=plan_sources,
                            source_stage_record_id=plan_record.record_id)
                        brain.schedule_plan_review(config.task,plan,observation.observation_id,
                                                   plan_record.plan_id,plan_record.plan_version)
                        decision_boundary=brain.begin_stage("decision",observation.observation_id,
                            plan_id=plan_record.plan_id,plan_version=plan_record.plan_version)
                        if config.embedding_model:
                            decision_memories=await memory.retrieve_with_embeddings(config.task+" "+observation.html[:1500],config.memory_limit,provider,budget,config.embedding_model,log_call)
                        else:
                            decision_memories=list(memory.retrieve(config.task,config.memory_limit))
                        decision_memories=with_boundary_memories(decision_memories,decision_boundary,
                            4 if hasattr(provider,"choose") else 6)
                        decision=await brain.decide_action(config.task,observation,
                            decision_memories,perception,plan,previous_error,
                            config.max_steps-step_count,recent_actions=recent_actions)
                        decision_sources=[m["memory_id"] for m in decision_memories if "memory_id" in m]
                        decision_task_id=brain.fast_task_id("decision")
                        decision_record=write_fast_stage("decision",observation,decision.rationale_summary,
                            decision_sources,plan_id=plan_record.plan_id,
                            task_id=decision_task_id,
                            action=decision.action,finish=decision.finish)
                        brain.complete_fast("decision",decision_record)
                    decision_ms=int((time.monotonic()-decision_started)*1000)
                except BudgetExceeded:
                    step_count+=1
                    write_unexecuted_step(step_id,observation,pre_observed_at,
                        "budget_exceeded","Model request budget was exhausted.")
                    termination="budget_exceeded";break
                except TimeoutError:
                    step_count+=1
                    write_unexecuted_step(step_id,observation,pre_observed_at,
                        "run_timeout","Run deadline was reached during model decision.")
                    termination="run_timeout";break
                except Exception as exc:
                    step_count+=1
                    termination="model_error";previous_error={"code":"model_output_error","message":str(exc)[:400]}
                    write_unexecuted_step(step_id,observation,pre_observed_at,
                        previous_error["code"],previous_error["message"])
                    error_counts[previous_error["code"]]=error_counts.get(previous_error["code"],0)+1;break
                step_count+=1
                if decision.action is None:
                    evaluation=await evaluate_current(browser.active);verification=evaluation["verification"]
                    steps.write({"step_id":step_id,"observation_id":observation.observation_id,"decision":decision.model_dump(),"action":None,"result":None,"next_observation_id":observation.observation_id,"pre_observed_at":pre_observed_at,"post_observed_at":None,"recorded_at":datetime.now(timezone.utc).isoformat(),"memory_ids":decision_sources,"verification":verification,"evaluation":evaluation,"timing_ms":{"llm":decision_ms}})
                    termination="cancelled" if stop_requested() else "agent_finished" if decision.finish.claim=="completed" else "agent_gave_up"
                    break
                if stop_requested():
                    write_unexecuted_step(step_id,observation,pre_observed_at,
                        "cancelled","Run was stopped before action execution.",
                        decision=decision,memory_ids=decision_sources)
                    termination="cancelled";break
                if time.monotonic()>=run_deadline:
                    write_unexecuted_step(step_id,observation,pre_observed_at,
                        "run_timeout","Run deadline was reached before action execution.",
                        decision=decision,memory_ids=decision_sources)
                    termination="run_timeout";break
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
                    previous_error={"code":"post_observation_error","message":"Post-action observation could not be captured."}
                    error_counts[previous_error["code"]]=error_counts.get(previous_error["code"],0)+1
                    evaluation={"verification":"unknown","reason":"post_observation_error","feature_checks":[]};verification="unknown"
                    steps.write({"step_id":step_id,"observation_id":observation.observation_id,"decision_id":decision.decision_id,"action_id":action_result.action_id,"next_observation_id":None,"pre_observed_at":pre_observed_at,"post_observed_at":None,"recorded_at":datetime.now(timezone.utc).isoformat(),"decision":decision.model_dump(),"action":decision.action.model_dump(),"result":action_result.model_dump(),"verification":verification,"evaluation":evaluation,"error":previous_error,"timing_ms":{"llm":decision_ms,"action":action_result.elapsed_ms}})
                    termination="browser_error";break
                post_observed_at=datetime.now(timezone.utc).isoformat()
                last_obs=next_obs
                executor.publish(next_registry)
                evaluation=await evaluate_current(browser.active);verification=evaluation["verification"]
                fingerprint_state=next_obs.model_dump(exclude={"observation_id","capture","error","tabs"})
                fingerprint=hashlib.sha256(json.dumps(fingerprint_state,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                action_key=json.dumps({k:getattr(decision.action,k) for k in ("type","target_id","text","option_value","url","target_tab_id") if getattr(decision.action,k) is not None},sort_keys=True,ensure_ascii=False)
                repeated_key=fingerprint+action_key;seen[repeated_key]=seen.get(repeated_key,0)+1
                if seen[repeated_key]>=config.repeated_state_action_limit:termination="stuck"
                summary=f"{decision.action.type} {decision.action.target_id or decision.action.url or ''}: {'ok' if action_result.ok else action_result.error['code']}"
                memory.append("action",summary,[step_id],[observation.observation_id],"observed")
                mock_stage={"type":"type","click":"click-search","select":"select-color" if decision.action.option_value=="검정" else "select-price" if decision.action.option_value=="30000" else "apply-filter"}.get(decision.action.type,decision.action.type)
                # use semantic target to distinguish repeated select/click phases
                if decision.action.type=="click" and decision.action.target_id and "필터" in decision.action.target_id:mock_stage="apply-filter"
                step_history.append({"mock_stage":mock_stage,"summary":summary})
                steps.write({"step_id":step_id,"observation_id":observation.observation_id,"decision_id":decision.decision_id,"action_id":action_result.action_id,"next_observation_id":next_obs.observation_id,"pre_observed_at":pre_observed_at,"post_observed_at":post_observed_at,"recorded_at":datetime.now(timezone.utc).isoformat(),"decision":decision.model_dump(),"action":decision.action.model_dump(),"result":action_result.model_dump(),"memory_ids":decision_sources,"verification":verification,"evaluation":evaluation,"timing_ms":{"llm":decision_ms,"action":action_result.elapsed_ms,"observation":0,"settle":0}})
                if stop_requested():termination="cancelled";break
                if termination=="stuck":break
                if verification=="success":termination="verified_success";break
            else:termination="max_steps"
    except KeyboardInterrupt:
        termination="interrupted"
    except Exception as exc:
        termination="browser_error";previous_error={"code":"browser_error","message":str(exc)[:500]}
        error_counts["browser_error"]=error_counts.get("browser_error",0)+1
    finally:
        if brain: await brain.close()
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
    measured = measured_usage(call_records, budget.requests)
    for name, entry in measured['provider_usage'].items():
        provider_usage[name].update(entry)
    measured['provider_usage'] = provider_usage
    if len(call_records) != budget.requests:
        measured['cost_complete'] = False
    brain_summary=brain.summary() if brain else {"status":"incomplete","fast":{},"slow":{"status":"not_started","events":{}},"adoption":{}}
    summary={"run_id":run_id,"termination_reason":termination,"verification":verification,"evaluator":evaluation if 'evaluation' in locals() else {"verification":"unknown"},
             "steps":step_count,"action_attempts":action_attempts,"action_successes":action_successes,"llm_request_count":budget.requests,
             "llm_tokens":budget.tokens,"budget":budget.snapshot(),"model_routes":routes,
             "limits":{"max_steps":config.max_steps,"run_timeout_seconds":config.run_timeout_seconds},
             "cost":sum((entry["estimated_cost_usd"] or 0) for entry in provider_usage.values()) if all(entry["estimated_cost_usd"] is not None for entry in provider_usage.values()) else None,
             "provider_usage":provider_usage,"elapsed_ms":elapsed,"llm_ms":llm_elapsed_total,"back_count":back_count,"error_counts":error_counts,"last_error":previous_error,
             "provider":provider_name,"model":model,"condition":persona_mode,"brain_status":brain_summary["status"],"brain":brain_summary,"slow_loop_status":slow.status if slow else "not_started","importance_scoring_status":"pending" if any(entry.importance is None for entry in memory.entries) else "scored","started_at":now,"finished_at":datetime.now(timezone.utc).isoformat(),"last_observation_id":last_obs.observation_id if last_obs else None}
    from .metrics import run_metrics
    step_records=[json.loads(line) for line in (run_dir/"steps.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    summary.update(measured)
    summary["metrics"]=run_metrics(run_dir,step_records,attempted_count=action_attempts)
    write_json(run_dir/"summary.json",summary)
    steps.close();calls.close();memory_writer.close();memory_change_writer.close();brain_task_writer.close();brain_stage_writer.close();wonder_draw_writer.close()
    return run_dir,summary
