import asyncio
import json
from pathlib import Path

import pytest

from uxagent.fast_loop import FastLoop
from uxagent.llm import BudgetExceeded, BudgetManager, GeminiProvider, JevProvider
from uxagent.memory import MemoryStore
from uxagent.schemas import Persona
from uxagent.slow_loop import SlowLoop


ROOT = Path(__file__).resolve().parents[1]


def test_budget_exhaustion_identifies_request_and_token_limit():
    requests = BudgetManager(1, None)
    requests.reserve(10)
    requests.settle(10, 4)
    with pytest.raises(BudgetExceeded) as request_error:
        requests.reserve(10)
    assert request_error.value.reason_code == "request_limit"

    tokens = BudgetManager(None, 20)
    with pytest.raises(BudgetExceeded) as token_error:
        tokens.reserve(21)
    assert token_error.value.reason_code == "token_limit"


@pytest.mark.asyncio
async def test_fast_retry_records_every_attempt_with_actual_provider():
    class RetryProvider:
        model = "gemini-2.5-flash-lite"

        def __init__(self):
            self.attempts = 0

        async def complete(self, messages, model, temperature, max_tokens):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("provider_transient:ConnectionError")
            return '{"perception":"확인"}', {"model": model, "input_tokens": 10,
                                                "output_tokens": 3, "provider": "gemini"}

    provider = RetryProvider()
    budget = BudgetManager(2, None)
    records = []
    fast = FastLoop(provider, budget, provider.model, 0.2, 100, records.append)

    assert await fast._generate("perception", "Read page", {"persona": {}}) == {"perception": "확인"}
    assert budget.requests == provider.attempts == len(records) == 2
    assert [row["provider"] for row in records] == ["gemini", "gemini"]
    assert records[0]["error"] == "RuntimeError"
    assert records[0]["estimated_cost_usd"] is None
    assert records[1]["estimated_cost_usd"] is not None


@pytest.mark.asyncio
async def test_jev_generation_log_names_gemini_and_choice_route_names_typesafe():
    from uxagent.runner import model_routes

    class JevLikeProvider:
        model = "jev-latest"

        async def choose(self, state, candidates):
            raise AssertionError("This test only requests generation")

        async def complete(self, messages, model, temperature, max_tokens):
            return '{"perception":"확인"}', {"provider": "gemini", "model": model,
                                                "input_tokens": 20, "output_tokens": 4}

    records = []
    fast = FastLoop(JevLikeProvider(), BudgetManager(None, None),
                    "gemini-2.5-flash-lite", 0.2, 100, records.append)
    await fast._generate("perception", "Read page", {})

    assert records[0]["provider"] == "gemini"
    assert records[0]["model"] == "gemini-2.5-flash-lite"
    assert model_routes("jev", "gemini-2.5-flash-lite")["decision_choice"] == {
        "provider": "typesafe", "model": "jev-latest"}


@pytest.mark.asyncio
async def test_jev_provider_delegates_generation_to_selected_gemini_model(monkeypatch):
    seen = []

    async def complete(self, messages, model, temperature, max_tokens):
        seen.append(model)
        return '{"perception":"확인"}', {"model": model, "input_tokens": 2,
                                           "output_tokens": 1}

    monkeypatch.setattr(GeminiProvider, "complete", complete)
    _, usage = await JevProvider().complete([{"role": "user", "content": "{}"}],
                                             model="gemini-2.5-flash", max_tokens=100)

    assert seen == ["gemini-2.5-flash"]
    assert usage["provider"] == "gemini"


@pytest.mark.asyncio
async def test_slow_records_actual_provider_model_and_unknown_cost():
    class Provider:
        async def complete(self, messages, model, temperature, max_tokens):
            return '{"insights":[]}', {"provider": "gemini", "model": "gemini-2.5-flash",
                                       "input_tokens": 11, "output_tokens": 3}

    store = MemoryStore("run-provider")
    records = []
    persona = Persona.model_validate_json((ROOT / "configs/persona.json").read_text(encoding="utf-8"))
    slow = SlowLoop(Provider(), BudgetManager(None, None), "gemini-2.5-flash", 0.2,
                    100, store, call_log=records.append)
    slow.schedule_reflection(persona, "가방", "obs-1")
    await slow.worker

    assert len(records) == 1
    assert records[0]["provider"] == "gemini"
    assert records[0]["model"] == "gemini-2.5-flash"
    assert records[0]["estimated_cost_usd"] is None


@pytest.mark.asyncio
async def test_cancelled_slow_request_settles_budget_and_logs_attempt():
    gate = asyncio.Event()
    started = asyncio.Event()

    class BlockingProvider:
        async def complete(self, messages, model, temperature, max_tokens):
            started.set()
            await gate.wait()
            raise AssertionError("Cancelled request should not finish")

    records = []
    budget = BudgetManager(None, None)
    persona = Persona.model_validate_json((ROOT / "configs/persona.json").read_text(encoding="utf-8"))
    slow = SlowLoop(BlockingProvider(), budget, "gemini-2.5-flash-lite", 0.2,
                    100, MemoryStore("run-cancel"), call_log=records.append)
    slow.schedule_reflection(persona, "가방", "obs-1")
    await started.wait()

    await slow.close()

    assert budget.requests == 1 and budget.reserved_tokens == 0
    assert len(records) == 1
    assert records[0]["stage"] == "reflection"
    assert records[0]["error"] == "CancelledError"
    assert records[0]["estimated_cost_usd"] is None


@pytest.mark.asyncio
async def test_jev_without_generator_key_rejected_before_artifacts(tmp_path, monkeypatch):
    import uxagent.runner as runner
    from uxagent.runner import run_study

    monkeypatch.setattr(runner, "load_env_file", lambda *args: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only-placeholder")
    config = json.loads((ROOT / "configs/study.json").read_text(encoding="utf-8"))
    config["persona_file"] = str(ROOT / "configs/persona.json")
    study = tmp_path / "study.json"
    study.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="Gemini"):
        await run_study(study, "jev", None, False, tmp_path / "runs")
    assert not (tmp_path / "runs").exists()


@pytest.mark.asyncio
async def test_unsupported_jev_embedding_is_rejected_before_artifacts(tmp_path, monkeypatch):
    from uxagent.runner import run_study

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    config = json.loads((ROOT / "configs/study.json").read_text(encoding="utf-8"))
    config.update(persona_file=str(ROOT / "configs/persona.json"),
                  embedding_model="text-embedding-3-small")
    study = tmp_path / "study.json"
    study.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="embedding"):
        await run_study(study, "jev", None, False, tmp_path / "runs")
    assert not (tmp_path / "runs").exists()


@pytest.mark.asyncio
async def test_comparison_rejects_jev_without_generator_before_session_registration(tmp_path, monkeypatch):
    import uxagent.experiments as experiments

    monkeypatch.setattr(experiments, "load_env_file", lambda *args: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only-placeholder")
    personas = tmp_path / "personas.jsonl"
    personas.write_text((ROOT / "configs/persona.json").read_text(encoding="utf-8"),
                        encoding="utf-8")

    with pytest.raises(ValueError, match="Gemini"):
        await experiments.run_comparison(ROOT / "configs/study.json", personas,
                                         provider_name="jev", output_root=tmp_path / "runs")
    assert not (tmp_path / "runs").exists()


def test_dashboard_rejects_unsupported_embedding_before_starting_job(tmp_path, monkeypatch):
    from uxagent.monitor import Dashboard

    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    config = json.loads((ROOT / "configs/study.json").read_text(encoding="utf-8"))
    config.update(persona_file=str(ROOT / "configs/persona.json"),
                  embedding_model="text-embedding-3-small")
    study = tmp_path / "study.json"
    study.write_text(json.dumps(config), encoding="utf-8")
    dashboard = Dashboard(tmp_path / "runs", tmp_path / "personas", study)

    with pytest.raises(ValueError, match="embedding"):
        dashboard.start_job("compare", provider="gemini")
    assert dashboard.job is None


def test_general_comparison_blocks_unexpected_slow_persona_fields(monkeypatch):
    from uxagent.brain import Brain

    persona = Persona.model_validate_json((ROOT / "configs/persona.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(FastLoop, "_persona_context", staticmethod(
        lambda value, mode: value.model_dump()))
    class NoCallSlow:
        def schedule_reflection(self, *args, **kwargs):
            raise AssertionError("Blocked general context reached Slow")

    brain = Brain(None, NoCallSlow(), MemoryStore("run-general-guard"), persona,
                  persona_mode="general")

    with pytest.raises(ValueError, match="general condition"):
        brain.schedule_reflection("가방 찾기", "obs-1")


@pytest.mark.asyncio
async def test_jev_runner_uses_gemini_generation_and_typesafe_choice(tmp_path, monkeypatch):
    from uxagent import runner
    from uxagent.llm import MockProvider

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    mock = MockProvider()

    async def generate(self, messages, model, temperature, max_tokens):
        content, _ = await mock.complete(messages, model, temperature, max_tokens)
        return content, {"provider": "gemini", "model": model,
                         "input_tokens": 20, "output_tokens": 4}

    async def choose(self, state, candidates):
        selected = next(item for item in candidates if item["id"].startswith("click:"))
        return selected["id"], 0.95, {selected["id"]: 0.95}, {
            "model": "jev-latest", "input_tokens": 10, "output_tokens": 2}

    monkeypatch.setattr(JevProvider, "complete", generate)
    monkeypatch.setattr(JevProvider, "choose", choose)
    config = json.loads((ROOT / "configs/study.json").read_text(encoding="utf-8"))
    config.update(persona_file=str(ROOT / "configs/persona.json"), max_steps=2,
                  provider_model="gemini-2.5-flash-lite", enable_wonder=False)
    study = tmp_path / "study.json"
    study.write_text(json.dumps(config), encoding="utf-8")

    run_dir, summary = await runner.run_study(study, "jev", None, False, tmp_path / "runs")
    calls = [json.loads(line) for line in (run_dir / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()]

    stages = {row["stage"] for row in calls}
    assert {"perception", "plan", "reflection"} <= stages
    assert "decision" in stages
    assert not any(row["stage"] == "plan_review" for row in calls)
    # Empty text inputs bypass candidate selection so Gemini can decide how to
    # produce the required query; Jev is used only when a candidate can execute directly.
    assert not any(row["provider"] == "typesafe" for row in calls)
    assert all(row["provider"] == "gemini" and row["model"] == "gemini-2.5-flash-lite"
               for row in calls if row["stage"] in {"perception", "feedback", "plan", "reflection", "plan_review", "search_query"})
    assert summary["llm_request_count"] == len(calls)


@pytest.mark.asyncio
async def test_general_condition_isolated_across_all_generation_stages(tmp_path, monkeypatch):
    from uxagent.llm import MockProvider
    from uxagent.runner import run_study

    original = MockProvider.complete
    payloads = []

    async def capture(self, messages, model=None, temperature=0.2, max_tokens=1200):
        payloads.append(json.loads(messages[-1]["content"]))
        return await original(self, messages, model, temperature, max_tokens)

    monkeypatch.setattr(MockProvider, "complete", capture)
    config = json.loads((ROOT / "configs/study.json").read_text(encoding="utf-8"))
    config.update(persona_file=str(ROOT / "configs/persona.json"), max_steps=1,
                  wonder_seed=139)
    study = tmp_path / "study.json"
    study.write_text(json.dumps(config), encoding="utf-8")
    persona = Persona(persona_id="p46", background="PRIVATE_BACKGROUND_46",
                      digital_familiarity="PRIVATE_FAMILIARITY_46",
                      preferences=["PRIVATE_PREFERENCE_46"], constraints={"budget": 30000},
                      intent="가방 찾기")

    run_dir, summary = await run_study(study, "mock", persona, False, tmp_path / "runs",
                                       persona_mode="general")

    assert payloads
    assert all("PRIVATE_" not in json.dumps(payload, ensure_ascii=False) for payload in payloads)
    assert summary["model_routes"]["wonder"]["provider"] == "mock"
    assert summary["budget"]["max_requests"] is None
    assert json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["model_routes"] == summary["model_routes"]


@pytest.mark.asyncio
async def test_budget_stop_summary_records_exact_limit(tmp_path):
    from uxagent.runner import run_study

    config = json.loads((ROOT / "configs/study.json").read_text(encoding="utf-8"))
    config.update(persona_file=str(ROOT / "configs/persona.json"), max_llm_requests=1)
    study = tmp_path / "study.json"
    study.write_text(json.dumps(config), encoding="utf-8")

    _, summary = await run_study(study, "mock", None, False, tmp_path / "runs")

    assert summary["termination_reason"] == "budget_exceeded"
    assert summary["budget"]["last_exceeded_reason"] == "request_limit"
    assert summary["llm_request_count"] == summary["budget"]["requests"] == 1
