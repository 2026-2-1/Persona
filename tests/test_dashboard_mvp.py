import json
from pathlib import Path

import pytest

from uxagent.monitor import Dashboard
import uxagent.monitor as monitor

ROOT = Path(__file__).resolve().parents[1]


class Process:
    returncode = None
    def poll(self): return self.returncode
    def terminate(self): self.returncode = -15


@pytest.fixture
def setup(tmp_path, monkeypatch):
    commands = []
    process = Process()
    monkeypatch.setattr(monitor.subprocess,"Popen",lambda cmd, **kwargs: commands.append(cmd) or process)
    dashboard = Dashboard(tmp_path/"runs",tmp_path/"personas",ROOT/"configs/study.json")
    dashboard.personas_dir.mkdir()
    dashboard.personas_dir.joinpath("personas.jsonl").write_text((ROOT/"configs/persona.json").read_text(encoding="utf-8").replace("\n","")+"\n",encoding="utf-8")
    return dashboard, commands, process


def test_comparison_launch_and_invalid_checks_rejected(setup):
    dashboard, commands, _ = setup
    job = dashboard.start_job("compare", repetitions=2)
    assert "compare" in commands[-1]
    assert commands[-1][commands[-1].index("--repetitions")+1] == "2"
    assert job["kind"] == "compare"


def test_key_connection_is_explicit_validated_and_not_returned(setup, monkeypatch):
    dashboard, _, _ = setup
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(dashboard,"_verify_connection",lambda provider: None)
    response = dashboard.connect("live","test-key-not-returned")
    assert response["validated"]
    assert "test-key-not-returned" not in json.dumps(dashboard.state())
    assert not list(dashboard.runs_dir.rglob("*.env"))


def test_stop_marks_job_cancelled_without_completion(setup):
    dashboard, _, _ = setup
    dashboard.start_job("batch")
    state = dashboard.stop_job()
    assert state["status"] == "cancelled"
    assert dashboard._job_state()["status"] == "cancelled"


def test_invalid_evaluation_check_never_launches(setup):
    dashboard, commands, _ = setup
    with pytest.raises(ValueError):
        dashboard.start_job("batch",evaluation_checks=[{"id":"x","label":"X","kind":"visible"}])
    assert not commands


def test_nested_experiment_is_discoverable(setup):
    dashboard, _, _ = setup
    folder=dashboard.runs_dir/"nested"/"experiments"/"e1"
    folder.mkdir(parents=True)
    (folder/"experiment.json").write_text('{"experiment_id":"e1","started_at":"2026-10-09"}',encoding="utf-8")
    assert dashboard.experiments()[0]["experiment_id"]=="e1"


def test_scenario_job_has_no_key_or_persona_generation_requirement(setup,monkeypatch):
    dashboard,commands,_=setup
    for name in ('OPENAI_API_KEY','GEMINI_API_KEY','TYPESAFE_API_KEY','ANTHROPIC_API_KEY'):
        monkeypatch.delenv(name,raising=False)
    dashboard.personas_dir.joinpath('personas.jsonl').unlink()
    job=dashboard.start_job('scenario',provider='scenario',scenario_case='flow')
    assert 'scenario' in commands[-1]
    assert '--provider' not in commands[-1]
    assert job['provider']=='scenario'
    assert job['kind']=='scenario'
    with pytest.raises(ValueError):
        dashboard.start_scenario('../../.env')
