import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from uxagent.schemas import Action, StudyConfig
from uxagent.security import normalize_origin, origin_allowed
from uxagent.memory import MemoryStore
from uxagent.personas import generate_personas
from uxagent.runner import run_study, load_study
from uxagent.review import create_review, create_survey, interview
from uxagent.browser import BrowserSession
from uxagent.observation import observe
from uxagent.actions import ActionExecutor
from uxagent.runner import FixtureServer
from uxagent.llm import BudgetManager
from uxagent.llm import MockProvider, OpenAIProvider, load_env_file, estimate_cost_usd
from uxagent.fast_loop import FastLoop
from uxagent.slow_loop import SlowLoop
from uxagent.schemas import Persona
from uxagent.schemas import Observation, ElementInfo
import uxagent.runner as runner_module

ROOT=Path(__file__).resolve().parents[1]


def test_env_loader_preserves_existing_values_and_provider_costs(tmp_path, monkeypatch):
    env=tmp_path/".env"
    env.write_text("TYPESAFE_API_KEY=do-not-print\nGEMINI_API_KEY='test-value'\n",encoding="utf-8")
    monkeypatch.setenv("TYPESAFE_API_KEY","process-value")
    monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    load_env_file(env)
    assert __import__("os").environ["TYPESAFE_API_KEY"]=="process-value"
    assert __import__("os").environ["GEMINI_API_KEY"]=="test-value"
    assert estimate_cost_usd("typesafe",1_000_000,100)==0.042
    assert estimate_cost_usd("gemini",1_000_000,1_000_000)==0.5


@pytest.mark.asyncio
async def test_jev_choice_maps_to_action_and_low_confidence_falls_back():
    class JevThenGemini:
        model="jev-latest"
        def __init__(self, confidence): self.confidence=confidence; self.fallback_calls=0
        async def choose(self,state,candidates):
            self.candidate=candidates[0]
            return self.candidate["id"],self.confidence,{self.candidate["id"]:self.confidence}, {"model":"jev-test","input_tokens":10,"output_tokens":2}
        async def complete(self,messages,model,temperature,max_tokens):
            self.fallback_calls+=1
            payload=json.loads(messages[-1]["content"])
            self.fallback_reason=payload.get("fallback_reason")
            return json.dumps({"candidate_id":self.candidate["id"]}), {"model":"gemini-2.5-flash-lite","input_tokens":20,"output_tokens":5}

    persona=Persona.model_validate_json((ROOT/"configs/persona.json").read_text())
    observation=Observation(observation_id="o1",tab_id="t1",url="https://shop.test",title="Shop",html="",
        clickable_elements=[ElementInfo(id="search",role="button",name="검색")])
    provider=JevThenGemini(.9); records=[]; budget=BudgetManager(4,10000)
    result=await FastLoop(provider,budget,"gemini-2.5-flash-lite",.2,100,records.append).decide(persona,"가방 찾기",observation,[])
    assert result.action.type=="click" and provider.fallback_calls==0
    assert records[0]["provider"]=="typesafe"

    provider=JevThenGemini(.4);records=[];budget=BudgetManager(4,10000)
    result=await FastLoop(provider,budget,"gemini-2.5-flash-lite",.2,100,records.append).decide(persona,"가방 찾기",observation,[])
    assert result.action.type=="click" and provider.fallback_calls==1
    assert provider.fallback_reason=="low_confidence"
    assert records[-1]["fallback_reason"]=="low_confidence"


def test_origin_normalization_and_config_validation():
    assert normalize_origin("http://LOCALHOST:80/shop") == "http://localhost"
    assert origin_allowed("https://a.test/path", ["https://a.test"])
    assert not origin_allowed("https://a.test.evil/path", ["https://a.test"])
    raw=json.loads((ROOT/"configs/study.json").read_text())
    raw["max_steps"]=-1
    with pytest.raises(ValidationError):StudyConfig.model_validate(raw)


def test_action_rejects_extra_or_missing_fields():
    with pytest.raises(ValidationError):
        Action.model_validate({"type":"click","observation_id":"o","tab_id":"t","target_id":"x","selector":"button"})
    with pytest.raises(ValidationError):
        Action.model_validate({"type":"type","observation_id":"o","tab_id":"t","target_id":"x"})


def test_memory_retrieval_includes_unknown_importance_by_recency():
    now=[100.0]
    store=MemoryStore("r",clock=lambda:now[0])
    store.append("observation","검정 가방 가격 확인",importance=None)
    now[0]+=1
    store.append("action","검색 실행",importance=0)
    results=store.retrieve("검정 가방",limit=1)
    assert results[0]["text"]=="검정 가방 가격 확인"
    assert "retrieval_score" in results[0]


@pytest.mark.asyncio
async def test_memory_embeddings_are_cached_and_share_budget():
    class FakeEmbeddingProvider:
        def __init__(self):self.calls=[]
        async def embed(self,texts,model):
            self.calls.append(list(texts))
            return [[float(i+1),1.0] for i,_ in enumerate(texts)],{"model":model,"input_tokens":len(texts)*2}
    now=[10.0];store=MemoryStore("r",clock=lambda:now[0]);store.append("observation","페이지 가격 표시")
    provider=FakeEmbeddingProvider();budget=BudgetManager(10,10000)
    await store.retrieve_with_embeddings("가격 조건",8,provider,budget,"fake")
    await store.retrieve_with_embeddings("가격 조건",8,provider,budget,"fake")
    assert len(provider.calls)==1
    assert budget.requests==1 and budget.tokens==4


@pytest.mark.asyncio
async def test_fast_loop_repairs_invalid_json_once():
    class RepairProvider:
        def __init__(self):self.calls=0
        async def complete(self,messages,model,temperature,max_tokens):
            self.calls+=1
            if self.calls==1:return "not-json",{"model":"fake","input_tokens":1,"output_tokens":1}
            return json.dumps({"perception":"검색창","plan":"검색","rationale_summary":"과제 조건 검색","action":{"type":"type","observation_id":"o1","tab_id":"tab-1","target_id":"상품.검색","text":"가방"},"finish":None},ensure_ascii=False),{"model":"fake","input_tokens":1,"output_tokens":1}
    provider=RepairProvider();budget=BudgetManager(3,10000)
    persona=Persona.model_validate_json((ROOT/"configs/persona.json").read_text())
    observation={"observation_id":"o1","tab_id":"tab-1","input_elements":[{"id":"상품.검색"}]}
    from types import SimpleNamespace
    result=await FastLoop(provider,budget,"fake",0.2,100).decide(persona,"가방 검색",SimpleNamespace(model_dump=lambda:observation),[])
    assert result.action.target_id=="상품.검색"
    assert provider.calls==budget.requests==2


@pytest.mark.asyncio
async def test_slow_loop_uses_snapshot_and_appends_generated_memory():
    store=MemoryStore("r");source=store.append("observation","필터와 검색 결과를 확인",source_step_ids=[2])
    budget=BudgetManager(5,10000);provider=MockProvider();persona=Persona.model_validate_json((ROOT/"configs/persona.json").read_text())
    slow=SlowLoop(provider,budget,"mock-v1",0.2,1000,store)
    assert slow.schedule(persona,"상품을 찾는다") is True
    assert slow.schedule(persona,"상품을 찾는다") is False
    await slow.task
    assert slow.status=="completed"
    reflection=store.entries[-1]
    assert reflection.kind=="reflection" and reflection.content_status=="generated"
    assert reflection.based_on_seq==source.seq and reflection.source_step_ids==[2]
    assert budget.requests==1


@pytest.mark.asyncio
async def test_live_provider_requires_key_before_network(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY",raising=False)
    with pytest.raises(RuntimeError,match="OPENAI_API_KEY is required"):
        await OpenAIProvider().complete([],"model")


@pytest.mark.asyncio
async def test_runner_distinguishes_false_finish_and_repeated_state(monkeypatch,tmp_path):
    raw=json.loads((ROOT/"configs/study.json").read_text());raw["persona_file"]=str(ROOT/"configs/persona.json")
    study=tmp_path/"study.json";study.write_text(json.dumps(raw),encoding="utf-8")
    class FinishProvider:
        async def complete(self,*args,**kwargs):
            return json.dumps({"perception":"초기 화면","plan":"완료 여부를 확인한다","rationale_summary":"현재 결과는 조건에 맞지 않습니다.","action":None,"finish":{"claim":"completed","summary":"완료했다고 판단했습니다."}},ensure_ascii=False),{"model":"fake","input_tokens":1,"output_tokens":1}
    monkeypatch.setattr(runner_module,"MockProvider",FinishProvider)
    _,summary=await run_study(study,"mock",None,False,tmp_path/"false-finish")
    assert summary["termination_reason"]=="agent_finished"
    assert summary["verification"]=="failure"

    class RepeatingProvider:
        async def complete(self,messages,*args,**kwargs):
            payload=json.loads(messages[-1]["content"]);obs=payload["observation"]
            target=next(e for e in obs["clickable_elements"] if e["name"]=="검색")
            return json.dumps({"perception":"검색 버튼이 보인다","plan":"검색을 실행한다","rationale_summary":"화면에서 검색 버튼을 사용한다.","action":{"type":"click","observation_id":obs["observation_id"],"tab_id":obs["tab_id"],"target_id":target["id"]},"finish":None},ensure_ascii=False),{"model":"fake","input_tokens":1,"output_tokens":1}
    monkeypatch.setattr(runner_module,"MockProvider",RepeatingProvider)
    _,summary=await run_study(study,"mock",None,False,tmp_path/"repeated")
    assert summary["termination_reason"]=="stuck"
    assert summary["action_attempts"]==3


def test_persona_quota_is_seeded_and_content_is_unique(tmp_path):
    config=tmp_path/"personas.json"
    config.write_text(json.dumps({"count":6,"seed":42,"sampling_mode":"quota","example_persona_file":str(ROOT/"configs/persona.json"),"attributes":{"digital_familiarity":{"낮음":1/3,"보통":1/3,"높음":1/3}},"fixed_constraints":{"budget_krw":30000}}),encoding="utf-8")
    out,count,total=generate_personas(config,tmp_path)
    assert count==total==6
    manifest=json.loads((tmp_path/"generation_manifest.json").read_text())
    assert list(manifest["distributions"]["digital_familiarity"]["assigned"].values())==[2,2,2]
    assert len({json.loads(line)["background"] for line in out.read_text().splitlines()})==6


@pytest.mark.asyncio
async def test_mock_run_completes_and_review_artifacts_are_safe(tmp_path):
    run_dir,summary=await run_study(ROOT/"configs/study.json","mock",None,False,tmp_path)
    assert summary["termination_reason"]=="verified_success"
    assert summary["verification"]=="success"
    steps=[json.loads(line) for line in (run_dir/"steps.jsonl").read_text().splitlines()]
    assert len(steps)>=5
    assert all(s["observation_id"] and s["next_observation_id"] for s in steps if s.get("action"))
    path,issues=create_review(run_dir)
    document=path.read_text()
    assert "<script>" not in document
    assert list((run_dir/"observations").glob("*.png"))
    assert summary["llm_tokens"]==0
    assert summary["evaluator"]["verification"]=="success"
    survey=create_survey(run_dir)
    assert all(x["response"]["data_type"]=="simulated_self_report" for x in survey)
    result=interview(run_dir,2,"이때 무엇을 찾았나요?")
    assert set(result["source_step_ids"]).issubset({1,2})
    assert "실제로 무엇을 생각하거나 느꼈는지는 확인할 수 없습니다" in result["answer"]


@pytest.mark.asyncio
async def test_observation_hides_hidden_text_and_stale_ids_are_rejected():
    config,_,_=load_study(ROOT/"configs/study.json")
    server=FixtureServer(8000);started=server.start()
    try:
        async with BrowserSession(False,config.viewport.width,config.viewport.height) as browser:
            await browser.set_allowed_origins(config.allowed_origins)
            await browser.active.goto(config.start_url)
            first,registry=await observe(browser)
            assert "정답은 상품 내부 코드" not in first.html
            assert "테스트 숨김 옵션" not in first.html
            # Two equal visible labels receive distinct IDs within the same observation.
            await browser.active.evaluate("""() => {for(let i=0;i<2;i++){const b=document.createElement('button');b.textContent='같은 버튼';document.querySelector('main').append(b)}}""")
            second,second_registry=await observe(browser)
            duplicate_ids=[e.id for e in second.clickable_elements if e.name=="같은 버튼"]
            assert len(duplicate_ids)==2 and duplicate_ids[0]!=duplicate_ids[1]
            executor=ActionExecutor(browser,config.allowed_origins)
            executor.publish(second_registry)
            old_target=first.input_elements[0]
            result=await executor.execute(Action(type="type",observation_id=first.observation_id,tab_id=first.tab_id,target_id=old_target.id,text="가방"))
            assert not result.ok and result.error["code"]=="stale_observation"
            executor.publish(second_registry)
            blocked=await executor.execute(Action(type="navigate",observation_id=second.observation_id,tab_id=second.tab_id,url="http://127.0.0.1:8000/not-observed.html"))
            assert not blocked.ok and blocked.error["code"]=="target_not_found"
            # An allowed origin still cannot redirect navigation to an unobserved path.
            await browser.active.evaluate("""() => {const a=document.createElement('a');a.href='https://example.invalid/';a.textContent='External';document.querySelector('main').append(a)}""")
            third,third_registry=await observe(browser);executor.publish(third_registry)
            external=next(x for x in third.clickable_elements if x.name=="External")
            result=await executor.execute(Action(type="click",observation_id=third.observation_id,tab_id=third.tab_id,target_id=external.id))
            assert not result.ok and result.error["code"]=="navigation_blocked"
    finally:
        if started:server.close()


@pytest.mark.asyncio
async def test_mock_run_stops_when_request_budget_is_exhausted(tmp_path):
    raw=json.loads((ROOT/"configs/study.json").read_text())
    raw["persona_file"]=str(ROOT/"configs/persona.json")
    raw["max_llm_requests"]=1
    study=tmp_path/"study.json";study.write_text(json.dumps(raw),encoding="utf-8")
    _,summary=await run_study(study,"mock",None,False,tmp_path/"runs")
    assert summary["termination_reason"]=="budget_exceeded"
    assert summary["llm_request_count"]==1
    assert summary["verification"]=="failure"
