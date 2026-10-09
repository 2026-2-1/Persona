from pathlib import Path
import json

import pytest

from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager
from uxagent.review import derive_issues
from uxagent.schemas import ElementInfo, Observation, Persona


@pytest.mark.asyncio
async def test_select_candidate_choice_preserves_each_option():
    class SelectSecond:
        model = "jev-test"

        async def choose(self, state, candidates):
            ids = [item["id"] for item in candidates]
            assert len(set(ids)) == len(ids)
            return ids[1], .9, {ids[1]: .9}, {"input_tokens": 10, "output_tokens": 2}

        async def complete(self, *args):
            raise AssertionError("valid high-confidence choice must not fall back")

    persona = Persona.model_validate_json((Path(__file__).resolve().parents[1] / "configs/persona.json").read_text(encoding="utf-8"))
    obs = Observation(observation_id="o1", tab_id="t1", url="https://shop.test", title="", html="",
                      select_elements=[ElementInfo(id="color", role="combobox", name="색상",
                                                  options=[{"value": "black", "label": "검정"},
                                                           {"value": "white", "label": "흰색"}])])
    decision = await FastLoop(SelectSecond(), BudgetManager(3, 10000), "test", .2, 100).decide(persona, "가방 찾기", obs, [])
    assert decision.action.option_value == "white"
    assert decision.action.target_id == "color"


def test_issue_review_accepts_null_results_and_excludes_finish_from_repetition():
    steps = [{"step_id": i, "action": None, "result": None} for i in range(1, 4)]
    assert derive_issues(steps) == []
    steps += [{"step_id": i, "action": {"type": "click", "target_id": "search"},
               "result": {"error": None}} for i in range(4, 7)]
    issues = derive_issues(steps)
    assert len(issues) == 1
    assert issues[0]["evidence_step_ids"] == [4, 5, 6]


@pytest.mark.asyncio
async def test_general_prompt_keeps_constraints_without_persona_background():
    class Capture:
        async def complete(self, messages, *args):
            self.payload = json.loads(messages[1]["content"])
            return json.dumps({"perception":"page", "plan":"finish", "rationale_summary":"done",
                               "action":None, "finish":{"claim":"give_up","summary":"no target"}}), {"input_tokens":1,"output_tokens":1}
    persona = Persona(persona_id="p1", background="SECRET BACKGROUND", digital_familiarity="high",
                      preferences=["SECRET PREFERENCE"], constraints={"budget":30000}, intent="find bag")
    obs = Observation(observation_id="o", tab_id="t", url="https://shop.test", title="", html="")
    provider = Capture()
    await FastLoop(provider, BudgetManager(2, 10000), "test", .2, 100).decide(persona,"find bag",obs,[],persona_mode="general")
    assert provider.payload["persona"] == {"constraints":{"budget":30000},"intent":"find bag"}


@pytest.mark.asyncio
async def test_jev_generates_real_query_instead_of_typing_entire_task():
    class InputProvider:
        model = "jev-test"
        async def choose(self, *args):
            raise AssertionError("blank input requires generated text")
        async def complete(self, messages, *args):
            return json.dumps({"perception":"search", "plan":"query", "rationale_summary":"search bags",
                "action":{"type":"type","observation_id":"o","tab_id":"t","target_id":"search","text":"가방"},"finish":None}), {"input_tokens":1,"output_tokens":1}
    persona = Persona(persona_id="p1",background="student",digital_familiarity="normal",preferences=["black"],intent="bag")
    obs = Observation(observation_id="o",tab_id="t",url="https://shop.test",title="",html="",
                      input_elements=[ElementInfo(id="search",name="상품 검색",role="textbox",value="")])
    result = await FastLoop(InputProvider(),BudgetManager(2,10000),"test",.2,100).decide(persona,"3만원 이하 검은 가방 상세 확인",obs,[])
    assert result.action.text == "가방"


@pytest.mark.asyncio
async def test_jev_can_replace_a_prefilled_search_query():
    class CorrectQuery:
        model = "jev-test"
        async def choose(self, state, candidates):
            candidate=next(c for c in candidates if c["action"]["type"]=="type")
            return candidate["id"],.9,{candidate["id"]:.9},{"input_tokens":1,"output_tokens":1}
        async def complete(self,messages,*args):
            return json.dumps({"perception":"correct search", "plan":"replace query", "rationale_summary":"task mismatch",
                "action":{"type":"type","observation_id":"o","tab_id":"t","target_id":"search","text":"가방"},"finish":None}), {"input_tokens":1,"output_tokens":1}
    persona=Persona(persona_id="p",background="student",digital_familiarity="normal",preferences=["black"],intent="bag")
    obs=Observation(observation_id="o",tab_id="t",url="https://shop.test",title="",html="",
        input_elements=[ElementInfo(id="search",name="검색",role="textbox",value="wrong")],
        clickable_elements=[ElementInfo(id="button",name="검색",role="button")])
    result=await FastLoop(CorrectQuery(),BudgetManager(3,10000),"test",.2,100).decide(persona,"가방 찾기",obs,[])
    assert result.action.text=="가방"
