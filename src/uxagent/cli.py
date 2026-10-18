from __future__ import annotations

import argparse, asyncio, json, sys
from importlib.metadata import version as package_version
from pathlib import Path
from pydantic import ValidationError
from . import __version__
from .runner import load_study, run_study, FixtureServer
from .browser import BrowserSession
from .observation import observe
from .personas import generate_personas
from .review import create_review, interview
from .survey import create_survey, DEFAULT_QUESTIONNAIRE, Questionnaire
from .schemas import Action
from .actions import ActionExecutor
from .evaluator import evaluate


def _parser():
    parser=argparse.ArgumentParser(prog="uxagent",description="Local UX task exploration agent")
    parser.add_argument("--version",action="version",version=f"uxagent {__version__}")
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("doctor");p.add_argument("--study",default="configs/study.json")
    p=sub.add_parser("serve");p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8000)
    p=sub.add_parser("observe");p.add_argument("--study",default="configs/study.json");p.add_argument("--headless",action="store_true");p.add_argument("--output",default="runs/observe")
    p=sub.add_parser("act");p.add_argument("--study",default="configs/study.json");p.add_argument("--action",required=True,help="Action JSON file");p.add_argument("--headless",action="store_true")
    providers=["mock","jev","gemini","live","claude","gpu"]
    p=sub.add_parser("run");p.add_argument("--study",default="configs/study.json");p.add_argument("--provider",choices=providers,default="mock");p.add_argument("--headless",action="store_true");p.add_argument("--output",default="runs")
    p=sub.add_parser("personas");p.add_argument("--config",default="configs/personas.json");p.add_argument("--output",default=".");p.add_argument("--provider",choices=["mock","live"],default="mock")
    p=sub.add_parser("batch");p.add_argument("--study",default="configs/study.json");p.add_argument("--personas",default="personas.jsonl");p.add_argument("--provider",choices=providers,default="mock");p.add_argument("--survey-provider",choices=providers);p.add_argument("--questionnaire",default=str(DEFAULT_QUESTIONNAIRE));p.add_argument("--output",default="runs");p.add_argument("--stop-file")
    p=sub.add_parser("compare");p.add_argument("--study",default="configs/study.json");p.add_argument("--personas",required=True);p.add_argument("--provider",choices=providers,default="mock");p.add_argument("--repetitions",type=int,choices=[1,2,3],default=1);p.add_argument("--output",default="runs");p.add_argument("--stop-file")
    p=sub.add_parser("scenario",help="Run a preregistered browser scenario without any LLM API");p.add_argument("--config",default="configs/scenarios/decathlon-flow.json");p.add_argument("--output",default="runs");p.add_argument("--headed",action="store_true");p.add_argument("--defect",choices=["search","filter","reset","detail"]);p.add_argument("--study-id")
    p=sub.add_parser("dashboard",help="Open the local UXAgent run dashboard");p.add_argument("--port",type=int,default=8765);p.add_argument("--runs",default="runs");p.add_argument("--personas-dir",default="runs/personas");p.add_argument("--study",default="configs/study.json")
    group=p.add_mutually_exclusive_group()
    group.add_argument("--gpu-config", help="Private SSH/Slurm configuration; auto-detect runs/private/gpu-session.json")
    group.add_argument("--no-gpu",action="store_true",help="Disable automatic GPU allocation for this dashboard")
    p=sub.add_parser('gpu-password-setup',help='Save GPU SSH passwords once in macOS Keychain')
    p.add_argument('--gpu-config',default='runs/private/gpu-session.json')
    p=sub.add_parser('gpu-key-setup',help='Enroll a dedicated SSH public key once for automatic GPU startup')
    p.add_argument('--gpu-config',default='runs/private/gpu-session.json')
    p.add_argument('--identity-file',default='~/.ssh/uxagent_gpu_ed25519')
    p=sub.add_parser('gpu-key-unlock',help='Load the existing GPU SSH key into ssh-agent')
    p.add_argument('--gpu-config',default='runs/private/gpu-session.json')
    p=sub.add_parser("review");p.add_argument("--run",required=True)
    p=sub.add_parser("survey");p.add_argument("--run",required=True);p.add_argument("--questionnaire",default=str(DEFAULT_QUESTIONNAIRE));p.add_argument("--provider",choices=providers,default="gpu")
    p=sub.add_parser("interview");p.add_argument("--run",required=True);p.add_argument("--at-step",type=int,required=True);p.add_argument("--question",required=True)
    return parser


async def _doctor(study):
    errors=[]
    try:load_study(study)
    except Exception as exc:errors.append(f"study configuration: {exc}")
    try:
        import playwright
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True);await browser.close()
        browser_info=f"Chromium available (Playwright {package_version('playwright')})"
    except Exception as exc:errors.append(f"Playwright browser: {exc}");browser_info="not available"
    print(json.dumps({"python":sys.version.split()[0],"uxagent":__version__,"browser":browser_info,"study_errors":errors},ensure_ascii=False,indent=2))
    return 1 if errors else 0


async def _observe(study_path, headless, output):
    config,persona,_=load_study(study_path)
    from urllib.parse import urlsplit
    parsed=urlsplit(config.start_url);local=parsed.hostname in ("127.0.0.1","localhost") and parsed.path.endswith("shop.html")
    server=FixtureServer(parsed.port or 80) if local else None;started=server.start() if server else False
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    try:
        async with BrowserSession(not headless,config.viewport.width,config.viewport.height) as browser:
            await browser.active.goto(config.start_url,wait_until="domcontentloaded",timeout=config.action_timeout_ms)
            obs,registry=await observe(browser,out,config.max_observation_text,config.max_observation_elements)
            print(obs.model_dump_json(indent=2))
    finally:
        if server and started:server.close()


async def _act(study_path, action_path, headless):
    config,_,_=load_study(study_path);raw=json.loads(Path(action_path).read_text(encoding="utf-8"))
    from urllib.parse import urlsplit
    parsed=urlsplit(config.start_url);server=FixtureServer(parsed.port or 80) if parsed.path.endswith("shop.html") else None;started=server.start() if server else False
    try:
        async with BrowserSession(not headless,config.viewport.width,config.viewport.height) as browser:
            await browser.active.goto(config.start_url,wait_until="domcontentloaded")
            obs,registry=await observe(browser);raw["observation_id"]=obs.observation_id;raw["tab_id"]=obs.tab_id
            action=Action.model_validate(raw)
            executor=ActionExecutor(browser,config.allowed_origins,config.action_timeout_ms,config.settle_timeout_ms,allow_scroll=config.explicit_scroll)
            result=await executor.execute(action)
            print(result.model_dump_json(indent=2));return 0 if result.ok else 2
    finally:
        if server and started:server.close()


async def _batch(args):
    path=Path(args.personas)
    stop_file=getattr(args,"stop_file",None)
    questionnaire_path=Path(getattr(args,"questionnaire",None) or DEFAULT_QUESTIONNAIRE)
    questionnaire=Questionnaire.model_validate_json(questionnaire_path.read_text(encoding="utf-8")).model_dump(mode="json")
    personas=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip(): personas.append(__import__("uxagent.schemas",fromlist=["Persona"]).Persona.model_validate_json(line))
    results=[];request_total=token_total=0
    study_config,_,_=load_study(args.study)
    request_cap=study_config.max_llm_requests*len(personas) if study_config.max_llm_requests is not None else None
    token_cap=study_config.max_total_tokens*len(personas) if study_config.max_total_tokens is not None else None
    for persona in personas:
        if stop_file is not None and Path(stop_file).is_file():
            break
        if (request_cap is not None and request_total>=request_cap) or (token_cap is not None and token_total>=token_cap):
            results.append({"persona_id":persona.persona_id,"error":"batch_budget_exceeded"})
            continue
        try:
            stop_kwargs={"stop_file":stop_file} if stop_file is not None else {}
            run_dir,summary=await run_study(args.study,args.provider,persona,False,args.output,**stop_kwargs)
            request_total+=summary["llm_request_count"];token_total+=summary["llm_tokens"]
            result={"persona_id":persona.persona_id,"run_id":summary["run_id"],"termination_reason":summary["termination_reason"],"verification":summary["verification"],"run_dir":str(run_dir),"llm_request_count":summary.get("llm_request_count",0),"llm_tokens":summary.get("llm_tokens",0)}
            if summary["termination_reason"] in ("browser_error","model_error"):
                result["error"]=(summary.get("last_error") or {}).get("message",summary["termination_reason"])
            results.append(result)
        except Exception as exc:results.append({"persona_id":persona.persona_id,"error":str(exc)})
    survey_provider=getattr(args,"survey_provider",None) or args.provider
    for result in results:
        if "run_id" not in result:
            continue
        if stop_file is not None and Path(stop_file).is_file():
            result["survey_status"]="skipped_stopped"
            continue
        try:
            survey=await create_survey(result["run_dir"],questionnaire,provider_name=survey_provider)
            result["survey_status"]=survey["status"]
            if survey.get("error"):
                result["survey_error"]=survey["error"]
        except Exception as exc:
            result["survey_status"]="survey_error"
            result["survey_error"]={"code":type(exc).__name__}
        summary_path=Path(result["run_dir"])/"summary.json"
        if summary_path.is_file():
            updated=json.loads(summary_path.read_text(encoding="utf-8"))
            for key in ("llm_request_count","llm_tokens","provider_usage","survey"):
                if key in updated:
                    result[key]=updated[key]
    request_total=sum(int(result.get("llm_request_count",0) or 0) for result in results if "run_id" in result)
    token_total=sum(int(result.get("llm_tokens",0) or 0) for result in results if "run_id" in result)
    failed=sum("error" in r for r in results)
    survey_failed=sum(r.get("survey_status") not in (None,"completed","skipped_stopped") for r in results)
    total={"study_id":study_config.study_id,"requested":len(personas),"started":sum("run_id" in r for r in results),"verified_success":sum(r.get("verification")=="success" for r in results),"failed":failed,"survey_failed":survey_failed,"completed_with_failures":failed>0 or survey_failed>0,"llm_request_count":request_total,"llm_tokens":token_total,"budget":{"max_requests":request_cap,"max_tokens":token_cap},"runs":results}
    Path(args.output).mkdir(parents=True,exist_ok=True);(Path(args.output)/"batch_summary.json").write_text(json.dumps(total,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(total,ensure_ascii=False,indent=2));return 0


def main():
    args=_parser().parse_args()
    try:
        if args.command=="doctor":return asyncio.run(_doctor(args.study))
        if args.command=="serve":
            server=FixtureServer(args.port,args.host)
            if not server.start():print(f"Port {args.port} is already in use",file=sys.stderr);return 2
            print(f"Serving tests/fixtures at http://{args.host}:{args.port}",flush=True)
            try:server.server.serve_forever()
            except KeyboardInterrupt:pass
            finally:server.close()
            return 0
        if args.command=="observe":asyncio.run(_observe(args.study,args.headless,args.output));return 0
        if args.command=="act":return asyncio.run(_act(args.study,args.action,args.headless))
        if args.command=="run":
            run_dir,summary=asyncio.run(run_study(args.study,args.provider,None,not args.headless,args.output));print(json.dumps({"run_dir":str(run_dir),"summary":summary},ensure_ascii=False,indent=2));return 0 if summary["verification"]=="success" else 1
        if args.command=="personas":
            file,count,total=generate_personas(args.config,args.output,args.provider);print(f"Generated {count}/{total}: {file}");return 0 if count==total else 1
        if args.command=="batch":return asyncio.run(_batch(args))
        if args.command=="compare":
            from .experiments import run_comparison
            directory,summary=asyncio.run(run_comparison(args.study,args.personas,args.provider,args.repetitions,args.output,stop_file=args.stop_file))
            print(json.dumps({"experiment_dir":str(directory),"summary":summary},ensure_ascii=False,indent=2))
            return 1 if summary["system_errors"] else 0
        if args.command=="scenario":
            from .offline import run_scenario
            directory,summary=asyncio.run(run_scenario(args.config,output_root=args.output,headed=args.headed,defect=args.defect,study_id_override=args.study_id))
            print(json.dumps({"run_dir":str(directory),"summary":summary},ensure_ascii=False,indent=2))
            return 1 if summary["termination_reason"] in ("browser_error","scenario_action_error","run_timeout") else 0
        if args.command=="dashboard":
            from .monitor import serve_dashboard
            gpu_config = args.gpu_config
            if not args.no_gpu and gpu_config is None and Path('runs/private/gpu-session.json').is_file():
                gpu_config = 'runs/private/gpu-session.json'
            serve_dashboard(args.port,args.runs,args.personas_dir,args.study,gpu_config=gpu_config)
            return 0
        if args.command=='gpu-password-setup':
            from .gpu_passwords import setup_passwords
            setup_passwords(args.gpu_config)
            return 0
        if args.command=='gpu-key-setup':
            from .gpu_ssh_keys import setup_gpu_key
            setup_gpu_key(args.gpu_config,key_path=args.identity_file)
            return 0
        if args.command=='gpu-key-unlock':
            from .gpu_ssh_keys import unlock_gpu_key
            unlock_gpu_key(args.gpu_config)
            return 0
        if args.command=="review":
            file,issues=create_review(args.run);print(json.dumps({"review":str(file),"issue_candidates":len(issues)},ensure_ascii=False));return 0
        if args.command=="survey":
            questionnaire=Questionnaire.model_validate_json(Path(args.questionnaire).read_text(encoding="utf-8")).model_dump(mode="json")
            result=asyncio.run(create_survey(args.run,questionnaire,provider_name=args.provider))
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result["status"]=="completed" else 2
        if args.command=="interview":print(json.dumps(interview(args.run,args.at_step,args.question),ensure_ascii=False,indent=2));return 0
    except (ValidationError,ValueError,FileNotFoundError) as exc:
        print(f"error: {exc}",file=sys.stderr);return 2
    except KeyboardInterrupt:
        return 130
    return 0


if __name__=="__main__":raise SystemExit(main())
