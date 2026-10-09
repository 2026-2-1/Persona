import asyncio
import json
import urllib.error
import pytest
from uxagent import llm
from uxagent.monitor import Dashboard
from uxagent.reports import redact
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Response:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self):
        return json.dumps({'model': 'claude-sonnet-4-6', 'content': [{'type':'thinking','thinking':'hidden'}, {'type':'text','text':'{"ok":'}, {'type':'text','text':'true}'}], 'usage': {'input_tokens': 7, 'output_tokens': 4}}).encode()

def test_claude_messages_contract(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-anthropic-secret')
    calls = []
    monkeypatch.setattr(llm.urllib.request, 'urlopen', lambda request, **kwargs: calls.append(request) or Response())
    result, usage = asyncio.run(llm.ClaudeProvider().complete([{'role':'system','content':'JSON only'}, {'role':'user','content':'check'}], max_tokens=32))
    assert result == '{"ok":true}'
    assert usage == {'model':'claude-sonnet-4-6','input_tokens':7,'output_tokens':4}
    request = calls[0]
    assert request.full_url == 'https://api.anthropic.com/v1/messages'
    assert request.get_header('X-api-key') == 'test-anthropic-secret'
    assert request.get_header('Anthropic-version') == '2023-06-01'
    body = json.loads(request.data)
    assert body['system'] == 'JSON only'
    assert body['messages'] == [{'role':'user','content':'check'}]
    assert body['model'] == llm.ClaudeProvider.model
    assert body['max_tokens'] == 32
    assert llm.estimate_cost_usd('claude', 7, 4) is None

def test_claude_missing_key_before_network(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.setattr(llm.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('network called'))
    with pytest.raises(RuntimeError, match='ANTHROPIC_API_KEY is required'):
        asyncio.run(llm.ClaudeProvider().complete([{'role':'user','content':'check'}]))

@pytest.mark.parametrize('error, expected', [(urllib.error.HTTPError('url', 429, 'secret body', {}, None), 'provider_http_429'), (urllib.error.URLError(TimeoutError()), 'provider_transient:TimeoutError')])
def test_claude_errors_safe(monkeypatch, error, expected):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-secret')
    def fail(*a, **k): raise error
    monkeypatch.setattr(llm.urllib.request, 'urlopen', fail)
    with pytest.raises(RuntimeError, match=expected):
        asyncio.run(llm.ClaudeProvider().complete([{'role':'user','content':'check'}]))

def test_claude_connection_rollback_and_redaction(tmp_path, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'old-secret')
    dashboard = Dashboard(tmp_path/'runs', tmp_path/'personas', ROOT/'configs/study.json')
    def fail(provider): raise RuntimeError('new-secret')
    monkeypatch.setattr(dashboard, '_verify_connection', fail)
    with pytest.raises(ValueError, match='연결 확인에 실패'):
        dashboard.connect('claude', 'new-secret')
    import os
    assert os.environ['ANTHROPIC_API_KEY'] == 'old-secret'
    monkeypatch.setattr(dashboard, '_verify_connection', lambda provider: None)
    assert dashboard.connect('claude', 'new-secret')['validated']
    assert dashboard.state()['providers']['claude']
    assert 'new-secret' not in json.dumps(dashboard.state())
    assert redact({'error':'new-secret'}) == {'error':'[redacted]'}
    log = tmp_path/'log.txt'
    log.write_text('error: new-secret', encoding='utf-8')
    assert 'new-secret' not in dashboard._job_error(log, 1)

def test_claude_verify_uses_execution_model(tmp_path, monkeypatch):
    dashboard = Dashboard(tmp_path/'runs', tmp_path/'personas', ROOT/'configs/study.json')
    calls = []
    async def complete(self, messages, **kwargs): calls.append(kwargs); return '{}', {}
    monkeypatch.setattr(llm.ClaudeProvider, 'complete', complete)
    dashboard._verify_connection('claude')
    assert calls[0]['model'] == llm.ClaudeProvider.model

def test_claude_runtime_routes_and_logs_usage(tmp_path, monkeypatch):
    import uxagent.runner as runner
    captures = []
    def fast(provider, budget, model, temperature, max_tokens, log_call):
        captures.append((provider, model))
        log_call({'model':model, 'input_tokens':7, 'output_tokens':4})
        return object()
    class UnavailableBrowser:
        def __init__(self, *args): pass
        async def __aenter__(self): raise RuntimeError('test browser unavailable')
        async def __aexit__(self, *args): pass
    monkeypatch.setattr(runner, 'FastLoop', fast)
    monkeypatch.setattr(runner, 'BrowserSession', UnavailableBrowser)
    monkeypatch.setattr(runner.FixtureServer, 'start', lambda self: False)
    directory, summary = asyncio.run(runner.run_study(ROOT/'configs/study.json', 'claude', output_root=tmp_path))
    assert isinstance(captures[0][0], llm.ClaudeProvider)
    assert captures[0][1] == llm.ClaudeProvider.model
    assert summary['provider_usage']['claude']['estimated_cost_usd'] is None
    assert summary['cost'] is None
    assert summary['model'] == llm.ClaudeProvider.model
    assert json.loads((directory/'run.json').read_text(encoding='utf-8'))['model'] == llm.ClaudeProvider.model

def test_claude_start_requires_key_before_launch(tmp_path, monkeypatch):
    dashboard = Dashboard(tmp_path/'runs', tmp_path/'personas', ROOT/'configs/study.json')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    import uxagent.monitor as monitor
    monkeypatch.setattr(monitor.subprocess, 'Popen', lambda *a, **k: pytest.fail('process launched'))
    with pytest.raises(ValueError, match='claude 실행에 필요한 API 키'):
        dashboard.start_job('batch', provider='claude')

def test_claude_historical_key_is_redacted_without_env(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    assert redact('sk-ant-api03-' + 'a'*64) == '[redacted]'

def test_claude_overload_is_retryable(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-secret')
    def fail(*args, **kwargs): raise urllib.error.HTTPError('url', 529, 'overloaded', {}, None)
    monkeypatch.setattr(llm.urllib.request, 'urlopen', fail)
    with pytest.raises(RuntimeError, match='provider_transient:provider_http_529'):
        asyncio.run(llm.ClaudeProvider().complete([{'role':'user','content':'check'}]))

def test_claude_tls_error_is_not_retried(monkeypatch):
    import ssl
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-secret')
    def fail(*args, **kwargs): raise urllib.error.URLError(ssl.SSLCertVerificationError())
    monkeypatch.setattr(llm.urllib.request, 'urlopen', fail)
    with pytest.raises(RuntimeError, match='provider_tls_error:certificate_verification_failed'):
        asyncio.run(llm.ClaudeProvider().complete([{'role':'user','content':'check'}]))
@pytest.mark.asyncio
async def test_actual_fast_loop_labels_claude_usage():
    from uxagent.fast_loop import FastLoop
    from uxagent.llm import BudgetManager
    from uxagent.schemas import Persona, Observation
    class Provider:
        model = "claude-sonnet-4-6"
        async def complete(self, *args):
            return json.dumps({"perception":"page","plan":"finish","rationale_summary":"no target","action":None,
                "finish":{"claim":"give_up","summary":"no target"}}), {"model":self.model,"input_tokens":7,"output_tokens":4}
    persona=Persona(persona_id="p",background="student",digital_familiarity="normal",preferences=["black"],intent="bag")
    observation=Observation(observation_id="o",tab_id="t",url="https://example.test",title="",html="")
    calls=[]
    await FastLoop(Provider(),BudgetManager(2,10000),Provider.model,.2,100,calls.append).decide(persona,"bag",observation,[])
    assert calls[0]["provider"] == "claude"
    assert calls[0]["estimated_cost_usd"] is None
