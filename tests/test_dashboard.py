import json
from pathlib import Path

import pytest

from uxagent.monitor import Dashboard
from uxagent.personas import generate_personas
from uxagent.runner import load_study
import uxagent.monitor as monitor

ROOT = Path(__file__).resolve().parents[1]


class Process:
    returncode = None

    def poll(self):
        return self.returncode


@pytest.fixture
def dashboard(tmp_path, monkeypatch):
    process = Process()
    commands = []

    def launch(command, **kwargs):
        commands.append(command)
        return process

    monkeypatch.setattr(monitor.subprocess, "Popen", launch)
    d = Dashboard(tmp_path / "runs", tmp_path / "personas", ROOT / "configs/study.json")
    d.personas_dir.mkdir()
    d.personas_dir.joinpath("personas.jsonl").write_text((ROOT / "configs/persona.json").read_text().replace("\n", "") + "\n")
    return d, process, commands


def test_batch_snapshot_resolves_persona_after_relocation(dashboard):
    d, _, commands = dashboard
    url = "http://127.0.0.1:8000/shop.html?dashboard-check=1"
    job = d.start_job("batch", start_url=url, task="검정 가방 상세 확인")
    command = commands[-1]
    config, persona, path = load_study(command[command.index("--study") + 1])
    assert path.parent == d.runs_dir / ".dashboard"
    assert Path(config.persona_file).is_absolute()
    assert persona.persona_id == "p001"
    assert config.start_url == url and config.task == "검정 가방 상세 확인"
    assert config.allowed_origins == ["http://127.0.0.1:8000"]
    assert config.study_id == job["study_id"]
    assert d._job_state()["status"] == "running"  # Starting a job must not deadlock.


def test_generation_uses_form_input_and_avoids_unrelated_old_run(dashboard):
    d, process, commands = dashboard
    old = d.runs_dir / "old-run"
    old.mkdir(parents=True)
    old.joinpath("run.json").write_text('{"started_at":"2020-01-01"}')
    old.joinpath("persona.json").write_text((ROOT / "configs/persona.json").read_text())
    old.joinpath("summary.json").write_text('{"verification":"success"}')
    task = "2~3만원 검은색 바람막이의 사이즈와 상세 정보를 확인한다."
    background = "20대 초반 남성, 키 178cm, 몸무게 90kg."
    d.start_job("generate", persona_count=2, persona_background=background, task=task)
    command = commands[-1]
    generated, count, total = generate_personas(command[command.index("--config") + 1], d.personas_dir)
    assert count == total == 2
    personas = [json.loads(line) for line in generated.read_text().splitlines()]
    assert all(background in p["background"] and p["intent"] == task for p in personas)
    process.returncode = 0
    state = d.state()
    assert state["job"]["status"] == "completed"
    assert state["job"]["message"] == "페르소나 2명 생성 완료"
    assert all(p["run"] is None for p in state["personas"])
    assert state["generation"]["task"] == task
    assert state["generation"]["background"] == background


def test_latest_observation_and_nested_run_are_visible(dashboard):
    d, _, _ = dashboard
    run = d.runs_dir / "decathlon-test" / "nested-run"
    obs = run / "observations"
    obs.mkdir(parents=True)
    run.joinpath("run.json").write_text('{"started_at":"2026-01-01"}')
    run.joinpath("steps.jsonl").write_text('{"observation_id":"obs-old","next_observation_id":"obs-old"}\n')
    obs.joinpath("obs-old.json").write_text('{"url":"https://site.test/old"}')
    obs.joinpath("obs-new.json").write_text('{"url":"https://site.test/new"}')
    # Ensure the new observation wins even if it hasn't been linked to a completed step yet.
    import os
    os.utime(obs / "obs-old.json", ns=(1, 1))
    obs.joinpath("obs-new.png").write_bytes(b"test-image")
    run_state = next(r for r in d.state()["runs"] if r["run_id"] == "nested-run")
    assert run_state["latest_observation_id"] == "obs-new"
    assert run_state["latest_url"] == "https://site.test/new"
    assert d.run_detail("nested-run")["observations"]["obs-new"]["screenshot_url"]
    assert d.run_detail("../../.env") is None


def test_failed_job_explains_error_without_exposing_key(dashboard, monkeypatch):
    d, process, _ = dashboard
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-no-output")
    d.start_job("generate")
    Path(d.job["log_path"]).write_text("error: missing persona.json test-secret-no-output\n")
    process.returncode = 2
    state = d.state()
    assert state["job"]["status"] == "failed"
    assert "missing persona.json" in state["job"]["message"]
    assert "test-secret-no-output" not in json.dumps(state)
    assert "process" not in state["job"] and "log_path" not in state["job"]


def test_invalid_setup_is_rejected_before_launch(dashboard):
    d, _, commands = dashboard
    with pytest.raises(ValueError, match="URL"):
        d.start_job("generate", start_url="")
    with pytest.raises(ValueError, match="올바른 URL"):
        d.start_job("generate", start_url="file:///etc/passwd")
    with pytest.raises(ValueError, match="Mock"):
        d.start_job("batch", start_url="https://shop.test")
    with pytest.raises(ValueError, match="1~12"):
        d.start_job("generate", persona_count=0)
    assert not commands


@pytest.mark.asyncio
async def test_batch_reports_browser_failure_instead_of_completion(dashboard, monkeypatch):
    from types import SimpleNamespace
    from uxagent.cli import _batch
    import uxagent.cli as cli

    d, _, _ = dashboard

    async def failed_run(*args):
        return d.runs_dir / "failed-run", {"run_id":"failed-run","termination_reason":"browser_error",
                "verification":"unknown","llm_request_count":0,"llm_tokens":0,
                "last_error":{"message":"navigation failed"}}

    monkeypatch.setattr(cli, "run_study", failed_run)
    args = SimpleNamespace(study=str(d.study), personas=str(d.personas_dir / "personas.jsonl"),
                           provider="mock", output=str(d.runs_dir))
    assert await _batch(args) == 1
    summary = json.loads((d.runs_dir / "batch_summary.json").read_text())
    assert summary["failed"] == 1
    assert summary["runs"][0]["error"] == "navigation failed"
