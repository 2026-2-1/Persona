import asyncio
import json
from pathlib import Path

import pytest

from uxagent.llm import LocalQwenProvider
from uxagent.model_catalog import resolve_model
from uxagent.monitor import Dashboard
import uxagent.monitor as monitor
from uxagent.runner import validate_gpu_fixture_port


def test_local_qwen_uses_tunnel_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PERSONA_QWEN_API_URL", "http://127.0.0.1:8000/v1/chat/completions")
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self):
            return json.dumps({"model": "persona-qwen", "choices": [{"message": {"content": "{\"ok\":true}"}}],
                               "usage": {"prompt_tokens": 24, "completion_tokens": 8}}).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr("uxagent.llm.urllib.request.urlopen", fake_urlopen)
    content, usage = asyncio.run(LocalQwenProvider().complete([{"role": "user", "content": "JSON으로 답하세요"}],
                                                              "persona-qwen", max_tokens=64))
    assert captured["url"] == "http://127.0.0.1:8000/v1/chat/completions"
    assert "Authorization" not in captured["headers"]
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["model"] == "persona-qwen"
    assert content == '{"ok":true}'
    assert usage == {"provider": "gpu", "model": "persona-qwen", "input_tokens": 24, "output_tokens": 8}
    assert resolve_model("gpu") == "persona-qwen"


def test_local_qwen_rejects_nonlocal_endpoint(monkeypatch):
    monkeypatch.setenv("PERSONA_QWEN_API_URL", "http://example.com:8000/v1/chat/completions")
    with pytest.raises(ValueError, match="로컬 SSH 터널"):
        LocalQwenProvider()._complete([], "persona-qwen", 0.2, 64)


def test_gpu_tunnel_cannot_take_fixture_port(monkeypatch):
    monkeypatch.setenv("PERSONA_QWEN_API_URL", "http://127.0.0.1:8000/v1/chat/completions")
    with pytest.raises(ValueError, match="같은 로컬 포트"):
        validate_gpu_fixture_port("http://127.0.0.1:8000/shop.html")
    validate_gpu_fixture_port("https://www.decathlon.co.kr/search?query=러닝화")
    monkeypatch.setenv("PERSONA_QWEN_API_URL", "http://127.0.0.1:8001/v1/chat/completions")
    validate_gpu_fixture_port("http://127.0.0.1:8000/shop.html")


def test_dashboard_connects_gpu_without_key(tmp_path, monkeypatch):
    study = Path(__file__).resolve().parents[1] / "configs/study.json"
    dashboard = Dashboard(tmp_path / "runs", tmp_path / "personas", study)
    seen = []
    monkeypatch.setattr(dashboard, "_verify_connection", lambda provider, model=None: seen.append((provider, model)))
    result = dashboard.connect("gpu", None, model="persona-qwen")
    assert seen == [("gpu", "persona-qwen")]
    assert result["validated"] is True
    assert dashboard.state()["providers"]["gpu"] is True
    assert dashboard.state()["connection_models"]["gpu"] == "persona-qwen"


def test_dashboard_snapshots_gpu_model_without_key(tmp_path, monkeypatch):
    study = Path(__file__).resolve().parents[1] / "configs/study.json"
    dashboard = Dashboard(tmp_path / "runs", tmp_path / "personas", study)
    dashboard.personas_dir.mkdir(parents=True)
    persona = Path(__file__).resolve().parents[1] / "configs/persona.json"
    (dashboard.personas_dir / "personas.jsonl").write_text(persona.read_text(encoding="utf-8").replace("\n", "") + "\n", encoding="utf-8")

    class Process:
        def poll(self):
            return None

    commands = []
    monkeypatch.setattr(monitor.subprocess, "Popen", lambda command, **kwargs: commands.append(command) or Process())
    job = dashboard.start_job("batch", provider="gpu", model="persona-qwen",
                              start_url="https://www.decathlon.co.kr/search?query=러닝화")
    snapshot = json.loads(Path(commands[-1][commands[-1].index("--study") + 1]).read_text(encoding="utf-8"))
    assert job["model"] == "persona-qwen"
    assert snapshot["provider_model"] == "persona-qwen"
    assert commands[-1][commands[-1].index("--provider") + 1] == "gpu"


def test_dashboard_snapshot_preserves_evaluation_profile_location(tmp_path, monkeypatch):
    study = Path(__file__).resolve().parents[1] / "configs/study-decathlon-live.json"
    dashboard = Dashboard(tmp_path / "runs", tmp_path / "personas", study)
    dashboard.personas_dir.mkdir(parents=True)
    persona = Path(__file__).resolve().parents[1] / "configs/persona.json"
    (dashboard.personas_dir / "personas.jsonl").write_text(
        persona.read_text(encoding="utf-8").replace("\n", "") + "\n", encoding="utf-8")

    class Process:
        def poll(self):
            return None

    commands = []
    monkeypatch.setattr(monitor.subprocess, "Popen", lambda command, **kwargs: commands.append(command) or Process())
    dashboard.start_job("batch", provider="gpu", model="persona-qwen")
    snapshot_path = Path(commands[-1][commands[-1].index("--study") + 1])
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    profile = Path(snapshot["evaluation_profile_file"])
    assert profile.is_absolute()
    assert profile == study.parent / "decathlon_live_profile.json"
    assert profile.is_file()
