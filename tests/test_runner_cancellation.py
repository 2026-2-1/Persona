"""Cancellation reaches the real runner; browser/model I/O is replaced locally."""
import asyncio
import json
from pathlib import Path

import pytest

import uxagent.runner as runner
from uxagent.schemas import Action, AgentDecision, Finish, Observation

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["browser_enter", "decision", "action", "brain_close", "final_capture", "browser_exit"])
async def test_real_task_cancellation_persists_final_result_and_closes_writers(tmp_path, monkeypatch, phase):
    events, writers = [], []
    ready = asyncio.Event()
    blocked = False

    async def checkpoint(name):
        nonlocal blocked
        if name == phase and not blocked:
            blocked = True
            ready.set()
            await asyncio.Future()

    class Page:
        url = "https://shop.test"
        async def goto(self, *_args, **_kwargs): pass
        async def wait_for_function(self, *_args, **_kwargs): pass

    class Browser:
        def __init__(self, *_args):
            self.active, self.closed = Page(), False
        async def __aenter__(self):
            await checkpoint("browser_enter")
            return self
        async def __aexit__(self, *_args):
            try:
                await checkpoint("browser_exit")
            finally:
                self.closed = True
                events.append("browser_closed")

    async def observe(browser, run_dir, *_args):
        assert not browser.closed
        final = "observed" in events
        if final:
            await checkpoint("final_capture")
            events.append("final_capture")
        else:
            events.append("observed")
        obs = Observation(observation_id="obs-final" if final else "obs-pre", tab_id="tab-1",
                          url=browser.active.url, title="합성 페이지", html="<p>합성</p>")
        runner.write_json(run_dir / "observations" / f"{obs.observation_id}.json", obs.model_dump())
        return obs, None

    async def forward(self, task, obs, *_args):
        await checkpoint("decision")
        outcome = {"action": Action(type="refresh", observation_id=obs.observation_id, tab_id=obs.tab_id)} \
            if phase == "action" else {"finish": Finish(claim="completed", summary="합성 종료")}
        return AgentDecision(decision_id="test", perception="합성", plan="합성", rationale_summary="합성", **outcome), []

    async def execute(self, action):
        await checkpoint("action")
        raise AssertionError("Cancelled action must not fabricate a result")

    original_close = runner.Brain.close
    async def close(self):
        await checkpoint("brain_close")
        await original_close(self)
        events.append("brain_closed")

    async def evaluate(page, *_args, **_kwargs):
        assert "brain_closed" in events and "browser_closed" not in events
        events.append("evaluated")
        return {"verification": "success", "reason": "synthetic_check", "feature_checks": []}

    class Writer(runner.JsonlWriter):
        def __init__(self, path):
            super().__init__(path)
            writers.append(self)

    config = json.loads((ROOT / "configs/study.json").read_text())
    config.update(start_url="https://shop.test", persona_file=str(ROOT / "configs/persona.json"))
    study = tmp_path / "study.json"
    runner.write_json(study, config)
    monkeypatch.setattr(runner, "BrowserSession", Browser)
    monkeypatch.setattr(runner, "observe", observe)
    monkeypatch.setattr(runner, "evaluate", evaluate)
    monkeypatch.setattr(runner.Brain, "forward", forward)
    monkeypatch.setattr(runner.Brain, "close", close)
    monkeypatch.setattr(runner.ActionExecutor, "execute", execute)
    monkeypatch.setattr(runner, "JsonlWriter", Writer)
    task = asyncio.create_task(runner.run_study(study, "mock", output_root=tmp_path / "runs"))
    try:
        await asyncio.wait_for(ready.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    folder = next((tmp_path / "runs").iterdir())
    assert (folder / "summary.json").exists(), "Actual cancellation must leave a summary"
    assert (folder / "final_evaluation.json").exists()
    summary = json.loads((folder / "summary.json").read_text())
    final = json.loads((folder / "final_evaluation.json").read_text())
    assert summary["termination_reason"] == final["termination_reason"] == "cancelled"
    assert "brain_closed" in events and all(writer.file.closed for writer in writers)
    assert summary["verification"] == final["evaluation"]["verification"]
    if phase in {"decision", "action", "browser_exit"}:
        assert final["observation_id"] == summary["final_observation_id"] == "obs-final"
        assert summary["verification"] == "success"
        assert events.index("brain_closed") < events.index("final_capture") < events.index("evaluated")
    else:
        assert summary["verification"] == "unknown" and final["observation_id"] is None
    assert summary["action_successes"] == 0
