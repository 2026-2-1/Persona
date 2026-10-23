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
    assert usage.pop('provider_queue_ms') >= 0
    assert usage.pop('prompt_guard')['checked'] is True
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
    monkeypatch.setattr(LocalQwenProvider, 'health', lambda *a, **kw: {'status': 'ok', 'model': 'persona-qwen'})
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
    monkeypatch.setattr(LocalQwenProvider, 'health', lambda *a, **kw: {'status': 'ok', 'model': 'persona-qwen'})
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


@pytest.mark.parametrize('url,changed_task,expected', [
    ('https://www.decathlon.co.kr/', False, 'decathlon-detail_basic-v1'),
    ('https://www.decathlon.co.kr/', True, 'unverified-external-site'),
    ('https://another-shop.test/', False, 'unverified-external-site'),
])
def test_dashboard_uses_known_decathlon_evaluator_only_for_registered_task(tmp_path, monkeypatch, url, changed_task, expected):
    root = Path(__file__).resolve().parents[1]
    preset = json.loads((root / 'configs/study-decathlon-live.json').read_text())
    dashboard = Dashboard(tmp_path / 'runs', tmp_path / 'personas', root / 'configs/study.json')
    dashboard.personas_dir.mkdir(parents=True)
    (dashboard.personas_dir / 'personas.jsonl').write_text((root / 'configs/persona.json').read_text().replace('\n', '') + '\n')
    monkeypatch.setattr(LocalQwenProvider, 'health', lambda *a, **kw: {})
    commands = []
    class Process:
        def poll(self): return None
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda command, **kw: commands.append(command) or Process())
    task = preset['task'].replace('8만원', '5만원') if changed_task else preset['task']
    dashboard.start_job('batch', provider='gpu', start_url=url, task=task)
    snapshot = json.loads(Path(commands[-1][commands[-1].index('--study') + 1]).read_text())
    assert snapshot['evaluator_id'] == expected
    if expected.startswith('decathlon-'):
        assert snapshot['evaluation_expectations']['max_price'] == 80000
        assert Path(snapshot['evaluation_profile_file']).is_absolute()
        assert snapshot['run_timeout_seconds'] is None
    else:
        assert snapshot['evaluation_expectations'] is None
        assert snapshot['evaluation_profile_file'] is None
        assert snapshot['run_timeout_seconds'] is None


def test_dashboard_preserves_custom_deadline_for_registered_gpu_task(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / 'configs/study.json').read_text())
    config.update(run_timeout_seconds=123, persona_file=str(root / 'configs/persona.json'))
    custom = tmp_path / 'study.json'
    custom.write_text(json.dumps(config))
    preset = json.loads((root / 'configs/study-decathlon-live.json').read_text())
    dashboard = Dashboard(tmp_path / 'runs', tmp_path / 'personas', custom)
    dashboard.personas_dir.mkdir(parents=True)
    (dashboard.personas_dir / 'personas.jsonl').write_text((root / 'configs/persona.json').read_text().replace('\n', '') + '\n')
    monkeypatch.setattr(LocalQwenProvider, 'health', lambda *a, **kw: {})
    commands = []
    class Process:
        def poll(self): return None
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda command, **kw: commands.append(command) or Process())
    dashboard.start_job('batch', provider='gpu', start_url='https://www.decathlon.co.kr/', task=preset['task'])
    snapshot = json.loads(Path(commands[-1][commands[-1].index('--study') + 1]).read_text())
    assert snapshot['run_timeout_seconds'] == 123


def test_disconnected_gpu_is_blocked_before_launch_and_status_is_invalidated(tmp_path, monkeypatch):
    dashboard = Dashboard(tmp_path / 'runs', tmp_path / 'personas', Path(__file__).resolve().parents[1] / 'configs/study.json')
    dashboard.connection_models['gpu'] = 'persona-qwen'
    def refused(*a, **kw):
        raise ConnectionRefusedError()
    monkeypatch.setattr(LocalQwenProvider, 'health', refused, raising=False)
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda *a, **kw: pytest.fail('must not launch a browser job'))
    with pytest.raises(ValueError, match='GPU 연결'):
        dashboard.start_job('batch', provider='gpu', model='persona-qwen', start_url='https://www.decathlon.co.kr/')
    assert not dashboard.state()['providers']['gpu']
    assert dashboard.state()['gpu_connection']['status'] == 'disconnected'
    assert dashboard.job is None
    assert not list((tmp_path / 'runs').rglob('*-study.json'))


def test_dashboard_recovers_gpu_before_launch_check(tmp_path, monkeypatch):
    dashboard = Dashboard(tmp_path / 'runs', tmp_path / 'personas', Path(__file__).resolve().parents[1] / 'configs/study.json')
    calls = []
    class GPU:
        def ensure_ready(self): calls.append('recover')
    dashboard.gpu_session = GPU()
    monkeypatch.setattr(LocalQwenProvider, 'health', lambda *a: calls.append('health'), raising=False)
    dashboard.ensure_gpu_connection()
    assert calls == ['recover', 'health']
    assert dashboard.gpu_connection['status'] == 'connected'


def test_connection_refused_is_transport_error_and_not_model_output(monkeypatch):
    import urllib.error
    from uxagent.llm import ProviderConnectionError
    def refused(*a, **kw):
        raise urllib.error.URLError(ConnectionRefusedError())
    monkeypatch.setattr('uxagent.llm.urllib.request.urlopen', refused)
    with pytest.raises(ProviderConnectionError, match='^provider_transient:ConnectionRefusedError$'):
        LocalQwenProvider()._complete([], 'persona-qwen', .2, 32)


def test_health_checks_actual_model_without_generation(monkeypatch):
    requests = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return b'{"status":"ok","model":"wrong-model"}'
    def urlopen(url, timeout):
        requests.append(url)
        return Response()
    monkeypatch.setenv('PERSONA_QWEN_API_URL', 'http://127.0.0.1:8001/v1/chat/completions')
    monkeypatch.setattr('uxagent.llm.urllib.request.urlopen', urlopen)
    with pytest.raises(ValueError, match='모델명'):
        LocalQwenProvider().health()
    assert requests == ['http://127.0.0.1:8001/health']


def test_background_monitor_invalidates_then_recovers_connection(tmp_path, monkeypatch):
    dashboard = Dashboard(tmp_path / 'runs', tmp_path / 'personas', Path(__file__).resolve().parents[1] / 'configs/study.json')
    dashboard.connection_models['gpu'] = 'persona-qwen'
    status = []
    class Stop:
        def wait(self, seconds):
            status.append(dashboard.gpu_connection['status'])
            return len(status) > 2
    calls = []
    def health(*a):
        calls.append('check')
        if len(calls) == 1:
            raise ConnectionRefusedError()
    monkeypatch.setattr(LocalQwenProvider, 'health', health)
    dashboard.maintain_gpu_connection(Stop())
    assert status == ['not_connected', 'disconnected', 'connected']


@pytest.mark.asyncio
async def test_gpu_sends_waiting_fast_before_slow_without_parallel_generations(monkeypatch):
    import threading
    provider = LocalQwenProvider()
    entered, release = threading.Event(), threading.Event()
    order = []
    active = peak = 0
    def complete(messages, *args):
        nonlocal active, peak
        stage = messages[0]['content']
        active += 1; peak = max(peak, active); order.append(stage)
        if stage == 'SLOW_STAGE:first':
            entered.set(); release.wait(3)
        active -= 1
        return '{}', {'provider': 'gpu', 'model': 'persona-qwen'}
    monkeypatch.setattr(provider, '_complete', complete)
    first = asyncio.create_task(provider.complete([{'role': 'system', 'content': 'SLOW_STAGE:first'}]))
    assert await asyncio.to_thread(entered.wait, 2)
    slow = asyncio.create_task(provider.complete([{'role': 'system', 'content': 'SLOW_STAGE:second'}]))
    fast = asyncio.create_task(provider.complete([{'role': 'system', 'content': 'FAST_STAGE:plan'}]))
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(first, slow, fast)
    assert order == ['SLOW_STAGE:first', 'FAST_STAGE:plan', 'SLOW_STAGE:second']
    assert peak == 1
    assert all(result[1]['provider_queue_ms'] >= 0 for result in results)


@pytest.mark.asyncio
async def test_cancelled_gpu_queue_item_is_never_sent(monkeypatch):
    import threading
    provider = LocalQwenProvider()
    entered, release = threading.Event(), threading.Event()
    calls = []
    def complete(messages, *args):
        calls.append(messages[0]['content'])
        if len(calls) == 1:
            entered.set(); release.wait(3)
        return '{}', {}
    monkeypatch.setattr(provider, '_complete', complete)
    first = asyncio.create_task(provider.complete([{'role': 'system', 'content': 'SLOW_STAGE:first'}]))
    assert await asyncio.to_thread(entered.wait, 2)
    queued = asyncio.create_task(provider.complete([{'role': 'system', 'content': 'FAST_STAGE:cancelled'}]))
    await asyncio.sleep(0)
    queued.cancel()
    with pytest.raises(asyncio.CancelledError): await queued
    release.set(); await first
    await asyncio.sleep(0)
    assert calls == ['SLOW_STAGE:first']


@pytest.mark.asyncio
async def test_cancelling_active_gpu_caller_does_not_send_next_until_request_finishes(monkeypatch):
    import threading
    provider = LocalQwenProvider()
    entered, release = threading.Event(), threading.Event()
    calls = []
    def complete(messages, *args):
        calls.append(messages[0]['content'])
        if len(calls) == 1:
            entered.set(); release.wait(3)
        return '{}', {}
    monkeypatch.setattr(provider, '_complete', complete)
    first = asyncio.create_task(provider.complete([{'role': 'system', 'content': 'SLOW_STAGE:first'}]))
    assert await asyncio.to_thread(entered.wait, 2)
    first.cancel()
    with pytest.raises(asyncio.CancelledError): await first
    second = asyncio.create_task(provider.complete([{'role': 'system', 'content': 'FAST_STAGE:second'}]))
    await asyncio.sleep(0)
    assert calls == ['SLOW_STAGE:first']
    release.set(); await second


@pytest.mark.asyncio
async def test_gpu_priority_keeps_a_turn_for_waiting_slow_requests(monkeypatch):
    import threading
    provider = LocalQwenProvider()
    entered, release = threading.Event(), threading.Event()
    order = []
    def complete(messages, *args):
        stage = messages[0]['content']; order.append(stage)
        if stage == 'SLOW_STAGE:first':
            entered.set(); release.wait(3)
        return '{}', {}
    monkeypatch.setattr(provider, '_complete', complete)
    first = asyncio.create_task(provider.complete([{'role': 'system', 'content': 'SLOW_STAGE:first'}]))
    assert await asyncio.to_thread(entered.wait, 2)
    slow = asyncio.create_task(provider.complete([{'role': 'system', 'content': 'SLOW_STAGE:waiting'}]))
    fast = [asyncio.create_task(provider.complete([{'role': 'system', 'content': f'FAST_STAGE:{i}'}])) for i in range(6)]
    await asyncio.sleep(0); release.set()
    await asyncio.gather(first, slow, *fast)
    assert order[:5] == ['SLOW_STAGE:first', 'FAST_STAGE:0', 'FAST_STAGE:1', 'FAST_STAGE:2', 'SLOW_STAGE:waiting']
