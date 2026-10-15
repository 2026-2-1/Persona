import json
from pathlib import Path

import pytest

from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager, estimate_cost_usd
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
async def test_staged_openai_prompts_explain_field_types_and_action_schema():
    class CapturingProvider:
        def __init__(self):
            self.systems = {}

        async def complete(self, messages, model, temperature, max_tokens):
            system = messages[0]["content"]
            stage = system.split("FAST_STAGE:", 1)[1].splitlines()[0]
            self.systems[stage] = system
            observation = json.loads(messages[1]["content"])["observation"]
            result = {"perception": {"perception": "검색창이 보입니다."},
                      "plan": {"plan": "검색어를 입력합니다."},
                      "decision": {"rationale_summary": "검색을 시작합니다.",
                                   "action": {"type": "type", "observation_id": observation["observation_id"],
                                              "tab_id": observation["tab_id"], "target_id": "search", "text": "가방"},
                                   "finish": None}}[stage]
            return json.dumps(result, ensure_ascii=False), {
                "model": "gpt-4o-mini-2024-07-18", "input_tokens": 1000, "output_tokens": 200}

    persona = Persona.model_validate_json((ROOT / "configs/persona.json").read_text())
    observation = Observation(observation_id="obs-current", tab_id="tab-current",
                              url="https://shop.test", title="Shop", html="검색",
                              input_elements=[ElementInfo(id="search", role="textbox", name="상품 검색")])
    provider = CapturingProvider()
    calls = []
    await FastLoop(provider, BudgetManager(3, 10000), "gpt-4o-mini", .2, 100, calls.append).decide(
        persona, "가방 찾기", observation, [])

    assert "perception must be a plain string" in provider.systems["perception"]
    assert "plan must be a plain string" in provider.systems["plan"]
    decision_prompt = provider.systems["decision"]
    assert "finish must be null or an object; never false" in decision_prompt
    assert "copy observation_id and tab_id from the current observation" in decision_prompt
    assert "select: target_id, option_value" in decision_prompt
    assert "type: target_id, text" in decision_prompt
    assert all(call["estimated_cost_usd"] == pytest.approx(.00027) for call in calls)


def test_openai_cost_catalog_only_prices_known_models():
    assert estimate_cost_usd("openai", 1_000_000, 1_000_000, "gpt-4o-mini") == .75
    assert estimate_cost_usd("openai", 1_000_000, 1_000_000, "gpt-4o-mini-2024-07-18") == .75
    assert estimate_cost_usd("openai", 100, 100, "gpt-unknown") is None


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
