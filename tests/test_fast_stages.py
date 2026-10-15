import json
from pathlib import Path

import pytest

from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager
from uxagent.runner import run_study
from uxagent.schemas import Observation, Persona, ElementInfo

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_fast_loop_generates_perception_plan_and_decision_as_separate_calls():
    class StageProvider:
        def __init__(self):
            self.stages = []

        async def complete(self, messages, model, temperature, max_tokens):
            stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0]
            self.stages.append(stage)
            obs = json.loads(messages[1]["content"])["observation"]
            outputs = {
                "perception": {"perception": "검색창과 검색 버튼이 보입니다."},
                "plan": {"plan": "과업에 맞는 검색어를 입력하고 검색합니다."},
                "decision": {
                    "rationale_summary": "검색어를 입력합니다.",
                    "action": {"type": "type", "observation_id": obs["observation_id"],
                               "tab_id": obs["tab_id"], "target_id": "search", "text": "가방"},
                    "finish": None,
                },
            }
            return json.dumps(outputs[stage], ensure_ascii=False), {
                "model": "stage-test", "input_tokens": 3, "output_tokens": 2,
            }

    persona = Persona.model_validate_json((ROOT / "configs/persona.json").read_text())
    observation = Observation(
        observation_id="obs-current", tab_id="tab-current", url="https://shop.test",
        title="Shop", html="검색", input_elements=[ElementInfo(id="search", role="textbox", name="상품 검색")],
    )
    provider = StageProvider()
    fast = FastLoop(provider, BudgetManager(5, 10000), "stage-test", .2, 100)

    perception = await fast.perceive(persona, "가방 찾기", observation, [])
    plan = await fast.plan(persona, "가방 찾기", observation, [], perception)
    decision = await fast.decide_action(
        persona, "가방 찾기", observation, [], perception, plan,
    )

    assert provider.stages == ["perception", "plan", "decision"]
    assert perception == "검색창과 검색 버튼이 보입니다."
    assert plan == "과업에 맞는 검색어를 입력하고 검색합니다."
    assert decision.action.observation_id == "obs-current"
    assert decision.action.target_id == "search"


@pytest.mark.asyncio
async def test_fast_stage_logs_usage_for_invalid_response_before_repair():
    class RepairProvider:
        model = "mock-v1"

        def __init__(self):
            self.responses = iter(['{"wrong": "shape"}', '{"perception": "검색 화면입니다."}'])

        async def complete(self, messages, model, temperature, max_tokens):
            return next(self.responses), {"model": self.model, "input_tokens": 3,
                                          "output_tokens": 2}

    persona = Persona.model_validate_json((ROOT / "configs/persona.json").read_text())
    observation = Observation(observation_id="obs-current", tab_id="tab-current",
                              url="https://shop.test", title="Shop", html="검색")
    budget = BudgetManager(5, 10000)
    calls = []
    fast = FastLoop(RepairProvider(), budget, "mock-v1", .2, 100, calls.append)

    assert await fast.perceive(persona, "가방 찾기", observation, []) == "검색 화면입니다."
    assert budget.requests == 2
    assert [call["stage"] for call in calls] == ["perception", "perception"]
    assert sum(call["input_tokens"] for call in calls) == 6


@pytest.mark.asyncio
async def test_jev_input_fallback_accepts_finish_claim():
    class TypeCandidateProvider:
        model = "jev-latest"

        async def choose(self, payload, candidates):
            selected = next(candidate for candidate in candidates if candidate["id"].startswith("type:"))
            return selected["id"], .9, {selected["id"]: .9}, {
                "model": self.model, "input_tokens": 3, "output_tokens": 2,
            }

        async def complete(self, messages, model, temperature, max_tokens):
            return json.dumps({"rationale_summary": "진행할 수 없습니다.", "action": None,
                               "finish": {"claim": "give_up", "summary": "진행할 수 없습니다."}}), {
                "model": "gemini-2.5-flash-lite", "input_tokens": 3, "output_tokens": 2,
            }

    persona = Persona.model_validate_json((ROOT / "configs/persona.json").read_text())
    observation = Observation(observation_id="obs-current", tab_id="tab-current",
                              url="https://shop.test", title="Shop", html="검색",
                              input_elements=[ElementInfo(id="search", role="textbox",
                                                          name="상품 검색", value="기존 검색어")])
    fast = FastLoop(TypeCandidateProvider(), BudgetManager(3, 10000),
                    "gemini-2.5-flash-lite", .2, 100)

    decision = await fast.decide_action(persona, "가방 찾기", observation, [],
                                        "검색창이 보입니다.", "검색어를 다시 입력합니다.")
    assert decision.action is None
    assert decision.finish.claim == "give_up"


@pytest.mark.asyncio
async def test_runner_records_fast_stages_and_saves_them_before_next_stage(tmp_path):
    run_dir, summary = await run_study(ROOT / "configs/study.json", "mock", None, False, tmp_path)
    stages = [json.loads(line) for line in (run_dir / "brain_stages.jsonl").read_text().splitlines()]
    step = json.loads((run_dir / "steps.jsonl").read_text().splitlines()[0])

    assert [record["stage"] for record in stages[:3]] == ["perception", "plan", "decision"]
    assert all(record["observation_id"] == step["observation_id"] for record in stages[:3])
    assert stages[1]["source_memory_ids"]
    assert stages[2]["plan_id"] == stages[1]["plan_id"]
    assert step["decision"]["perception"] == stages[0]["text"]
    assert step["decision"]["plan"] == stages[1]["text"]
    assert summary["verification"] == "success"
