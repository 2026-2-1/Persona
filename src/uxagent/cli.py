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
from .review import create_review, create_survey, interview
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
    providers=["mock","jev","gemini","live","claude"]
    p=sub.add_parser("run");p.add_argument("--study",default="configs/study.json");p.add_argument("--provider",choices=providers,default="mock");p.add_argument("--headless",action="store_true");p.add_argument("--output",default="runs")
    p=sub.add_parser("personas");p.add_argument("--config",default="configs/personas.json");p.add_argument("--output",default=".");p.add_argument("--provider",choices=["mock","live"],default="mock")
    p=sub.add_parser("batch");p.add_argument("--study",default="configs/study.json");p.add_argument("--personas",default="personas.jsonl");p.add_argument("--provider",choices=providers,default="mock");p.add_argument("--output",default="runs")
    p=sub.add_parser("compare");p.add_argument("--study",default="configs/study.json");p.add_argument("--personas",required=True);p.add_argument("--provider",choices=providers,default="mock");p.add_argument("--repetitions",type=int,choices=[1,2,3],default=1);p.add_argument("--output",default="runs")
    p=sub.add_parser("dashboard",help="Open the local UXAgent run dashboard");p.add_argument("--port",type=int,default=8765);p.add_argument("--runs",default="runs");p.add_argument("--personas-dir",default="runs/personas");p.add_argument("--study",default="configs/study.json")
    p=sub.add_parser("review");p.add_argument("--run",required=True)
    p=sub.add_parser("survey");p.add_argument("--run",required=True)
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
            await browser.set_allowed_origins(config.allowed_origins)
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
            await browser.set_allowed_origins(config.allowed_origins)
            await browser.active.goto(config.start_url,wait_until="domcontentloaded")
            obs,registry=await observe(browser);raw["observation_id"]=obs.observation_id;raw["tab_id"]=obs.tab_id
            action=Action.model_validate(raw)
            executor=ActionExecutor(browser,config.allowed_origins,config.action_timeout_ms,config.settle_timeout_ms);executor.publish(registry)
            result=await executor.execute(action)
            print(result.model_dump_json(indent=2));return 0 if result.ok else 2
    finally:
        if server and started:server.close()


async def _batch(args):
    path=Path(args.personas)
    personas=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip(): personas.append(__import__("uxagent.schemas",fromlist=["Persona"]).Persona.model_validate_json(line))
    results=[];request_total=token_total=0
    study_config,_,_=load_study(args.study)
    request_cap=study_config.max_llm_requests*len(personas)
    token_cap=study_config.max_total_tokens*len(personas)
    for persona in personas:
        if request_total>=request_cap or token_total>=token_cap:
            results.append({"persona_id":persona.persona_id,"error":"batch_budget_exceeded"})
            continue
        try:
            run_dir,summary=await run_study(args.study,args.provider,persona,False,args.output)
            request_total+=summary["llm_request_count"];token_total+=summary["llm_tokens"]
            result={"persona_id":persona.persona_id,"run_id":summary["run_id"],"termination_reason":summary["termination_reason"],"verification":summary["verification"],"run_dir":str(run_dir)}
            if summary["termination_reason"] in ("browser_error","model_error"):
                result["error"]=(summary.get("last_error") or {}).get("message",summary["termination_reason"])
            results.append(result)
        except Exception as exc:results.append({"persona_id":persona.persona_id,"error":str(exc)})
    total={"study_id":study_config.study_id,"requested":len(personas),"started":sum("run_id" in r for r in results),"verified_success":sum(r.get("verification")=="success" for r in results),"failed":sum("error" in r for r in results),"llm_request_count":request_total,"llm_tokens":token_total,"budget":{"max_requests":request_cap,"max_tokens":token_cap},"runs":results}
    Path(args.output).mkdir(parents=True,exist_ok=True);(Path(args.output)/"batch_summary.json").write_text(json.dumps(total,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(total,ensure_ascii=False,indent=2));return 1 if total["failed"] else 0


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
            run_dir,summary=asyncio.run(run_study(args.study,args.provider,None,not args.headless,args.output));print(json.dumps({"run_dir":str(run_dir),"summary":summary},ensure_ascii=False,indent=2));return 0 if summary["termination_reason"]=="verified_success" else 1
        if args.command=="personas":
            file,count,total=generate_personas(args.config,args.output,args.provider);print(f"Generated {count}/{total}: {file}");return 0 if count==total else 1
        if args.command=="batch":return asyncio.run(_batch(args))
        if args.command=="compare":
            from .experiments import run_comparison
            directory,summary=asyncio.run(run_comparison(args.study,args.personas,args.provider,args.repetitions,args.output))
            print(json.dumps({"experiment_dir":str(directory),"summary":summary},ensure_ascii=False,indent=2))
            return 1 if summary["system_errors"] else 0
        if args.command=="dashboard":
            from .monitor import serve_dashboard
            serve_dashboard(args.port,args.runs,args.personas_dir,args.study)
            return 0
        if args.command=="review":
            file,issues=create_review(args.run);print(json.dumps({"review":str(file),"issue_candidates":len(issues)},ensure_ascii=False));return 0
        if args.command=="survey":print(json.dumps(create_survey(args.run),ensure_ascii=False,indent=2));return 0
        if args.command=="interview":print(json.dumps(interview(args.run,args.at_step,args.question),ensure_ascii=False,indent=2));return 0
    except (ValidationError,ValueError,FileNotFoundError) as exc:
        print(f"error: {exc}",file=sys.stderr);return 2
    except KeyboardInterrupt:
        return 130
    return 0


if __name__=="__main__":raise SystemExit(main())
