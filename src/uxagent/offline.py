"""Bounded, preregistered browser scenarios. No LLM provider is instantiated."""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlencode

from pydantic import Field, model_validator

from .actions import ActionExecutor
from .browser import BrowserSession
from .decathlon_eval import evaluate_decathlon
from .evaluator import evaluate
from .metrics import run_metrics
from .observation import observe
from .runner import FixtureServer
from .schemas import StrictModel, Action, ActionResult, EvaluationCheck, Viewport
from .security import normalize_origin, origin_allowed
from .storage import JsonlWriter, write_json


class ScenarioStep(StrictModel):
    label: str = Field(min_length=1, max_length=200)
    type: Literal['click','type','keypress','scroll','select','navigate','back','check']
    target_name: str | None = None
    target_role: str | None = None
    target_selector: str | None = Field(default=None, max_length=1000)
    target_index: int | None = Field(default=None, ge=0, le=100)
    input_mode: Literal['fill','sequential'] | None = None
    settle_for_ms: int = Field(default=0, ge=0, le=1500)
    text: str | None = Field(default=None, max_length=2000)
    key: Literal['Enter','Escape','Tab','ArrowUp','ArrowDown','Space'] | None = None
    scroll_y: int | None = Field(default=None, ge=-900, le=900, strict=True)
    option_value: str | None = None
    url: str | None = None
    check: str | None = None
    expectations: dict = Field(default_factory=dict)
    dom_checks: list[EvaluationCheck] = Field(default_factory=list, max_length=10)
    optional: bool = False
    target_timeout_ms: int = Field(default=4000, ge=0, le=15000)
    checkpoint_timeout_ms: int = Field(default=2000, ge=100, le=10000)

    @model_validator(mode='after')
    def action_fields(self):
        if self.check and self.dom_checks:
            raise ValueError('use a task check or DOM checks, not both')
        if self.type=='check':
            if not (self.check or self.dom_checks) or self.optional:
                raise ValueError('passive check requires a checkpoint and cannot be optional')
            if any(getattr(self,k) is not None for k in ('text','key','scroll_y','option_value','url','input_mode','target_name','target_role','target_selector','target_index')):
                raise ValueError('passive check forbids action fields')
            return self
        if self.type in ('click','type','keypress','select') and not any((self.target_name,self.target_role,self.target_selector)):
            raise ValueError('target name, role or trusted selector is required')
        if self.optional and (self.check or self.dom_checks):
            raise ValueError('optional steps cannot declare required checkpoints')
        if self.check and self.dom_checks:
            raise ValueError('use a task check or DOM checks, not both')
        payload={'type':self.type,'observation_id':'validation','tab_id':'validation'}
        if self.type in ('click','type','keypress','select'):payload['target_id']='validation'
        payload.update({key:getattr(self,key) for key in ('text','key','scroll_y','option_value','url','input_mode') if getattr(self,key) is not None})
        Action.model_validate(payload)
        return self


class OfflineStudy(StrictModel):
    study_id: str = Field(min_length=1, max_length=100)
    task: str = Field(min_length=1, max_length=2000)
    fixture: Literal['decathlon.html'] | None = None
    start_url: str | None = None
    allowed_origins: list[str] = Field(default_factory=list)
    profile_file: str | None = None
    steps: list[ScenarioStep] = Field(min_length=1, max_length=50)
    viewport: Viewport = Field(default_factory=Viewport)
    run_timeout_seconds: float = Field(default=180, gt=0, le=600)
    warmup_ms: int = Field(default=0, ge=0, le=3000)
    max_observation_elements: int = Field(default=400, ge=50, le=1000)
    action_timeout_ms: int = Field(default=10000, ge=100, le=30000)
    settle_timeout_ms: int = Field(default=3000, ge=200, le=5000)

    @model_validator(mode='after')
    def target_scope(self):
        if not self.fixture:
            parsed=urlsplit(self.start_url or '')
            if parsed.scheme!='https' or parsed.hostname not in {'www.decathlon.co.kr','decathlon.co.kr'} or parsed.username or parsed.password:
                raise ValueError('live scenarios require an explicit public Decathlon HTTPS URL')
            if not self.profile_file or not self.allowed_origins:
                raise ValueError('live scenarios require selector profile and allowed origins')
            if normalize_origin(self.start_url) not in [normalize_origin(x) for x in self.allowed_origins]:
                raise ValueError('start URL must be in allowed origins')
        elif self.start_url or self.allowed_origins:
            raise ValueError('synthetic fixture receives an isolated local origin at execution')
        return self


async def resolve_target(step, observation, registry):
    groups={'type':['input_elements'], 'select':['select_elements'],
            'click':['clickable_elements'], 'keypress':['input_elements','clickable_elements','select_elements']}
    candidates={item.id:item for group in groups.get(step.type,[]) for item in getattr(observation,group)}
    matches=[]
    for identifier,item in candidates.items():
        if not item.enabled or step.target_name is not None and item.name!=step.target_name:
            continue
        if step.target_role is not None and item.role!=step.target_role:
            continue
        if step.target_selector:
            binding=registry.targets[identifier]
            try:
                if not await binding.locator.evaluate('(element, selector) => element.matches(selector)',step.target_selector):continue
            except Exception:
                raise ValueError('trusted target selector is invalid or detached') from None
        matches.append(identifier)
    if step.target_index is not None:
        return matches[step.target_index] if step.target_index<len(matches) else None
    if len(matches)>1:
        raise ValueError('ambiguous observed target; define a role or explicit index')
    return matches[0] if matches else None


async def checkpoint(page, step, profile):
    if step.dom_checks:
        return await evaluate(page,'offline-dom',step.dom_checks)
    if step.check:
        return await evaluate_decathlon(page,step.check,step.expectations,profile)
    return None


async def readonly_policy(action, registry):
    """Reject known consequential controls in this explicitly read-only mode."""
    blocked_label=re.compile(r'로그인|회원가입|결제|구매하기|바로\s*구매|주문하기|장바구니|담기|sign\s*in|check\s*out|add\s*to\s*cart|buy\s*now',re.I)
    blocked_path=re.compile(r'/(?:login|signin|checkout|cart|order|payment)(?:[/?.#-]|$)',re.I)
    if action.url and blocked_path.search(action.url):return False
    binding=registry.targets.get(action.target_id or '')
    if not binding:return True
    metadata=await binding.locator.evaluate("e => ({name:e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||'',type:e.getAttribute('type')||'',href:e.getAttribute('href')||'',form:e.closest('form')?.getAttribute('action')||''})")
    if blocked_label.search(metadata['name']) or blocked_path.search(metadata['href']) or blocked_path.search(metadata['form']):return False
    if action.type in ('type','keypress') and metadata['type'].lower() in ('password','email','tel','file'):return False
    return True


async def run_scenario(config_path, *, output_root='runs', headed=False, defect=None, study_id_override=None):
    path=Path(config_path).resolve()
    config=OfflineStudy.model_validate_json(path.read_text(encoding='utf-8'))
    if defect not in (None,'search','filter','reset','detail'):raise ValueError('unknown fixture defect')
    if defect and not config.fixture:raise ValueError('defects are only available in the synthetic fixture')
    profile=json.loads((path.parent/config.profile_file).resolve().read_text(encoding='utf-8')) if config.profile_file else None
    server=FixtureServer(0) if config.fixture else None
    started_server=False
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
    folder=Path(output_root)/run_id
    folder.mkdir(parents=True,exist_ok=False)
    source='synthetic_fixture' if config.fixture else 'live_configured'
    run_meta={'run_id':run_id,'study_id':study_id_override or config.study_id,'started_at':datetime.now(timezone.utc).isoformat(),
              'provider':'scenario','model':None,'execution_mode':'scripted','condition':'scenario','source_kind':source}
    write_json(folder/'run.json',run_meta)
    write_json(folder/'config.json',{**config.model_dump(),'execution_mode':'scripted','source_kind':source,'defect':defect})
    write_json(folder/'persona.json',{'persona_id':'scenario','intent':config.task,'execution_mode':'scripted'})
    writers=[JsonlWriter(folder/name) for name in ('steps.jsonl','llm_calls.jsonl','memory.jsonl')]
    steps_writer=writers[0]
    history=[];features=[];attempts=successes=0;termination='scenario_completed';error=None
    current_record=None
    browser_session=None;browser_entered=False
    started=time.monotonic();deadline=started+config.run_timeout_seconds
    try:
        if server:
            started_server=server.start()
            port=server.server.server_address[1]
            origin=f'http://127.0.0.1:{port}'
            start_url=f'{origin}/{config.fixture}'+('?' + urlencode({'defect':defect}) if defect else '')
            allowed=[origin]
        else:
            start_url=config.start_url;allowed=config.allowed_origins
        browser_session=BrowserSession(headed,config.viewport.width,config.viewport.height)
        async with asyncio.timeout(max(0, deadline-time.monotonic())):
            async with browser_session as browser:
                browser_entered=True
                await browser.set_allowed_origins(allowed)
                await browser.active.goto(start_url,wait_until='domcontentloaded',timeout=config.action_timeout_ms)
                try:
                    await browser.active.wait_for_load_state('load',timeout=config.action_timeout_ms)
                except Exception:
                    pass
                if config.warmup_ms:await asyncio.sleep(config.warmup_ms/1000)
                executor=ActionExecutor(browser,allowed,config.action_timeout_ms,config.settle_timeout_ms,allow_scroll=True)
                for step_id,step in enumerate(config.steps,1):
                    if time.monotonic()>=deadline:raise TimeoutError
                    current_record={'step_id':step_id,'scenario_step':step.label,'observation_id':None,
                                    'next_observation_id':None,'action':None,'result':None,'decision':None,
                                    'verification':'unknown'}
                    pre,registry=await observe(browser,folder,max_elements=config.max_observation_elements)
                    pre_time=datetime.now(timezone.utc).isoformat()
                    current_record.update(observation_id=pre.observation_id,pre_observed_at=pre_time)
                    executor.publish(registry)
                    if step.type=='check':
                        evaluation=await checkpoint(browser.active,step,profile)
                        until=min(deadline,time.monotonic()+step.checkpoint_timeout_ms/1000)
                        while evaluation['verification']!='success' and time.monotonic()<until:
                            await asyncio.sleep(.1)
                            evaluation=await checkpoint(browser.active,step,profile)
                        post,_=await observe(browser,folder,max_elements=config.max_observation_elements)
                        linked=[{**f,'id':f'{step_id}-{f["id"]}','task_id':step.check or 'dom','step_id':step_id,'observation_id':post.observation_id,
                                 'evaluation_method':'code','reason':evaluation['reason']} for f in evaluation.get('feature_checks',[])]
                        record={'step_id':step_id,'scenario_step':step.label,'observation_id':pre.observation_id,'next_observation_id':post.observation_id,
                                'action':None,'result':None,'decision':None,'verification':evaluation['verification'],
                                'evaluation':{**evaluation,'feature_checks':linked}}
                        steps_writer.write(record);history.append(record);features.extend(linked);current_record=None
                        if evaluation['verification']=='unknown':termination='scenario_unverified';break
                        continue
                    target=await resolve_target(step,pre,registry) if step.type in ('click','type','keypress','select') else None
                    if target is None and not step.optional and step.type in ('click','type','keypress','select'):
                        until=min(deadline,time.monotonic()+step.target_timeout_ms/1000)
                        while target is None and time.monotonic()<until:
                            await asyncio.sleep(.2)
                            pre,registry=await observe(browser,folder,max_elements=config.max_observation_elements)
                            pre_time=datetime.now(timezone.utc).isoformat()
                            executor.publish(registry)
                            target=await resolve_target(step,pre,registry)
                    if not target and step.type in ('click','type','keypress','select'):
                        record={'step_id':step_id,'scenario_step':step.label,'observation_id':pre.observation_id,'action':None,'result':None,
                                'skipped':step.optional,'error':None if step.optional else {'code':'scenario_target_missing','message':'Current observation has no matching target'},'verification':'unknown'}
                        steps_writer.write(record);history.append(record);current_record=None
                        if step.optional:continue
                        termination='scenario_action_error';error=record['error'];break
                    payload={'type':step.type,'observation_id':pre.observation_id,'tab_id':pre.tab_id}
                    if target:payload['target_id']=target
                    payload.update({key:getattr(step,key) for key in ('text','key','scroll_y','option_value','url','input_mode') if getattr(step,key) is not None})
                    action=Action.model_validate(payload)
                    attempts+=1
                    current_record.update(action=action.model_dump(),observation_id=pre.observation_id,
                                          pre_observed_at=pre_time,post_observed_at=None,timing_ms={'action':None})
                    if await readonly_policy(action,registry):
                        result=await executor.execute(action)
                    else:
                        result=ActionResult(action_id='a-'+uuid.uuid4().hex[:10],observation_id=pre.observation_id,ok=False,
                            error={'code':'scenario_policy_blocked','message':'Read-only scenario cannot use sign-in, purchase, payment or personal-data controls'},
                            url_before=browser.active.url,url_after=browser.active.url,elapsed_ms=0)
                    successes+=int(result.ok)
                    record=current_record
                    record.update(result=result.model_dump(),timing_ms={'action':result.elapsed_ms})
                    try:
                        if step.settle_for_ms:await asyncio.sleep(step.settle_for_ms/1000)
                        evaluation=await checkpoint(browser.active,step,profile)
                        if evaluation and result.ok:
                            until=min(deadline,time.monotonic()+step.checkpoint_timeout_ms/1000)
                            while evaluation['verification']!='success' and time.monotonic()<until:
                                await asyncio.sleep(.1)
                                evaluation=await checkpoint(browser.active,step,profile)
                        post,_=await observe(browser,folder,max_elements=config.max_observation_elements)
                        record.update(next_observation_id=post.observation_id,post_observed_at=datetime.now(timezone.utc).isoformat())
                        if evaluation:
                            linked=[{**f,'id':f'{step_id}-{f["id"]}','task_id':step.check or 'dom','step_id':step_id,'observation_id':post.observation_id,'evaluation_method':'code','reason':evaluation['reason']} for f in evaluation.get('feature_checks',[])]
                            evaluation={**evaluation,'feature_checks':linked}
                            record.update(evaluation=evaluation,verification=evaluation['verification'])
                            features.extend(linked)
                        if not result.ok:record['error']=result.error
                    except Exception:
                        record['error']={'code':'post_observation_error','message':'Post-action capture or check unavailable'}
                        termination='browser_error'
                    steps_writer.write(record);history.append(record);current_record=None
                    if result.ok and record.get('evaluation',{}).get('verification')=='unknown':
                        termination='scenario_unverified';break
                    if not result.ok or termination=='browser_error':
                        termination='scenario_action_error' if not result.ok else termination
                        error=record.get('error');break
    except TimeoutError:
        termination='run_timeout'
        error={'code':'run_timeout','message':'Scenario exceeded its execution deadline'}
        if browser_session is not None and not browser_entered:
            # __aexit__ is not called automatically when cancellation interrupts __aenter__.
            try:
                await browser_session.__aexit__(None,None,None)
            except Exception:
                pass
        if current_record is not None:
            current_record.update(error=error,verification='unknown')
            steps_writer.write(current_record);history.append(current_record)
    except (KeyboardInterrupt,asyncio.CancelledError):
        termination='interrupted'
    except Exception as exc:
        termination='browser_error';error={'code':type(exc).__name__,'message':'Scenario could not complete; inspect configuration and browser evidence'}
    finally:
        if server and started_server:server.close()
        for writer in writers:writer.close()
    status='failure' if any(f['status']=='fail' for f in features) or termination=='scenario_action_error' else 'unknown'
    if termination=='run_timeout':status='unknown'
    if termination=='scenario_completed' and features and all(f['status']=='pass' for f in features):status='success'
    if termination=='scenario_completed' and status=='failure':termination='scenario_failed'
    summary={**run_meta,'termination_reason':termination,'verification':status,'steps':len(history),
             'action_attempts':attempts,'action_successes':successes,'llm_request_count':0,'llm_tokens':0,'cost':0,
             'provider_usage':{},'elapsed_ms':int((time.monotonic()-started)*1000),'last_error':error,
             'evaluator':{'verification':status,'reason':'preregistered_checkpoints','feature_checks':features},
             'metrics':run_metrics(folder,history,attempted_count=attempts),'finished_at':datetime.now(timezone.utc).isoformat()}
    write_json(folder/'summary.json',summary)
    return folder,summary
