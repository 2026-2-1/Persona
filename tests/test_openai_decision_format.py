import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetManager, estimate_cost_usd
from uxagent.schemas import Persona

ROOT = Path(__file__).resolve().parents[1]


class CapturingProvider:
    model = None  # OpenAIProvider exposes no model attribute; FastLoop labels it "openai".

    def __init__(self):
        self.messages = []

    async def complete(self, messages, model, temperature, max_tokens):
        self.messages.append(messages)
        return json.dumps({"perception": "검색창이 보인다", "plan": "가방 검색", "rationale_summary": "과업 조건",
                           "action": {"type": "type", "observation_id": "o1", "tab_id": "tab-1",
                                      "target_id": "상품.검색", "text": "가방"}, "finish": None},
                          ensure_ascii=False), {"model": "gpt-4o-mini-2024-07-18", "input_tokens": 1000, "output_tokens": 200}


async def _decide(provider, calls):
    persona = Persona.model_validate_json((ROOT / "configs/persona.json").read_text(encoding="utf-8"))
    observation = {"observation_id": "o1", "tab_id": "tab-1", "input_elements": [{"id": "상품.검색"}]}
    return await FastLoop(provider, BudgetManager(3, 10000), "gpt-4o-mini", 0.2, 100, calls.append).decide_action(
        persona, "가방 검색", SimpleNamespace(model_dump=lambda: observation, observation_id="o1", tab_id="tab-1"), [], "검색창", "가방 검색")


@pytest.mark.asyncio
async def test_fast_loop_prompt_states_decision_field_types():
    # Live gpt-4o-mini returned perception as an object and finish as false (run 20261014T153403-c958d7b5).
    provider = CapturingProvider()
    await _decide(provider, [])
    system = provider.messages[0][0]["content"]
    assert "rationale_summary is a short plain string" in system
    assert 'finish is null or {"claim": "completed" or "give_up", "summary": string}' in system
    assert "never false" in system
    # Second live run omitted observation_id and used value instead of option_value (run 20261014T154056-7b12da8f).
    assert "copy observation_id and tab_id from the current observation" in system
    assert "select: target_id, option_value" in system


@pytest.mark.asyncio
async def test_openai_fast_call_records_measured_cost():
    calls = []
    await _decide(CapturingProvider(), calls)
    assert calls[0]["provider"] == "openai"
    assert calls[0]["estimated_cost_usd"] == pytest.approx(1000 * 0.15 / 1_000_000 + 200 * 0.60 / 1_000_000)


def test_openai_catalog_model_costs():
    assert estimate_cost_usd("openai", 1_000_000, 1_000_000, model="gpt-4o-mini") == 0.75
    assert estimate_cost_usd("openai", 1_000_000, 1_000_000, model="gpt-4.1-mini") == 2.0
    assert estimate_cost_usd("openai", 1_000_000, 1_000_000, model="gpt-4o-mini-2024-07-18") == 0.75
    assert estimate_cost_usd("openai", 1_000_000, 1_000_000, model="gpt-4.1-mini-2025-04-14") == 2.0
    assert estimate_cost_usd("openai", 100, 100, model="gpt-4o-mini-unknown") is None
    assert estimate_cost_usd("openai", 100, 100, model="gpt-unknown") is None
    assert estimate_cost_usd("openai", None, 100, model="gpt-4o-mini") is None
