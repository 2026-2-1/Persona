import pytest
from uxagent.runner import measured_usage
from uxagent.metrics import aggregate_sessions

@pytest.mark.parametrize('records,requests,input_total,output_total,total', [
    ([{'provider':'fake','input_tokens':None,'output_tokens':None}],1,None,None,None),
    ([{'provider':'fake','input_tokens':10,'output_tokens':None}],1,10,None,None),
    ([{'provider':'fake','input_tokens':0,'output_tokens':0}],1,0,0,0),
    ([{'provider':'fake','input_tokens':10,'output_tokens':2}, {'provider':'fake'}],2,10,2,12),
    ([{'provider':'fake','input_tokens':10,'output_tokens':2}],2,10,2,12),
])
def test_actual_usage_coverage(records, requests, input_total, output_total, total):
    metadata = measured_usage(records, requests)
    row = {'condition':'general','llm_request_count':requests,'llm_tokens':999, **metadata}
    group = aggregate_sessions([row])['general']
    complete = len(records) == requests and all(r.get('input_tokens') is not None and r.get('output_tokens') is not None for r in records)
    assert group['llm_tokens'] == (total if complete else None)
    assert group['llm_tokens_known_total'] == total
    assert group['input_tokens_known_total'] == input_total
    assert group['output_tokens_known_total'] == output_total
    assert group['requested'] == 1
    assert group['llm_request_count'] == requests
    if len(records) != requests:
        assert group['provider_usage']['fake']['requests'] is None
        assert group['provider_usage']['fake']['requests_known_total'] == len(records)
    assert group['llm_tokens_unknown_sessions'] == (0 if complete else 1)

@pytest.mark.parametrize('mode', ['missing', 'partial', 'error', 'zero'])
def test_runner_comparison_persists_actual_usage(tmp_path, monkeypatch, mode):
    import asyncio
    import json
    from pathlib import Path
    from uxagent import runner
    from uxagent.experiments import run_comparison
    original = runner.MockProvider
    class FakeProvider(original):
        async def complete(self, *args, **kwargs):
            if mode == 'error':
                raise RuntimeError('fake provider error')
            content, usage = await super().complete(*args, **kwargs)
            if mode == 'missing':
                usage.pop('input_tokens'); usage.pop('output_tokens')
            elif mode == 'partial':
                usage['input_tokens'] = 10; usage.pop('output_tokens')
            return content, usage
    monkeypatch.setattr(runner, 'MockProvider', FakeProvider)
    import socket
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    raw = json.loads(Path('configs/study.json').read_text(encoding='utf-8').replace(':8000', ':' + str(port)))
    raw.update(persona_file=str(Path('configs/persona.json').resolve()), max_steps=1)
    study = tmp_path / 'study.json'; study.write_text(json.dumps(raw), encoding='utf-8')
    personas = tmp_path / 'personas.jsonl'
    personas.write_text(Path('configs/persona.json').read_text(encoding='utf-8').replace('\n', '') + '\n', encoding='utf-8')
    directory, result = asyncio.run(run_comparison(study, personas, output_root=tmp_path))
    saved = json.loads((directory / 'experiment.json').read_text(encoding='utf-8'))
    assert saved['groups'] == aggregate_sessions(saved['sessions'])
    for session in saved['sessions']:
        group = saved['groups'][session['condition']]
        assert session['llm_request_count'] == (2 if mode == 'error' else 7)
        assert group['llm_request_count'] == session['llm_request_count']
        assert group['requested'] == 1
        assert group['recording']['attempted'] == session['metrics']['recording']['attempted']
        assert session['llm_tokens_complete'] is (mode == 'zero')
        assert group['llm_tokens'] == (0 if mode == 'zero' else None)
        assert group['llm_tokens_known_total'] == (0 if mode == 'zero' else None)
        assert group['input_tokens'] == (70 if mode == 'partial' else 0 if mode == 'zero' else None)
        assert group['output_tokens'] == (0 if mode == 'zero' else None)

@pytest.mark.parametrize('records, requests', [([], 1), ([{'provider':'fake','input_tokens':True,'output_tokens':2}], 1), ([{'provider':'fake','input_tokens':-1,'output_tokens':float('inf')}], 1)])
def test_unlogged_or_invalid_usage_never_establishes_full_total(records, requests):
    metadata = measured_usage(records, requests)
    assert metadata['llm_tokens_complete'] is False
    group = aggregate_sessions([{'condition':'general','llm_request_count':requests,'llm_tokens':500,**metadata}])['general']
    assert group['llm_tokens'] is None
    assert group['llm_tokens_known_total'] is None

def test_unlogged_request_cost_and_absent_provider_remain_unknown():
    measured = measured_usage([{'provider':'priced','input_tokens':10,'output_tokens':2,'estimated_cost_usd':0.125}], 2)
    rows = [{'condition':'general','llm_request_count':2,'llm_tokens':999,'cost':0.125,**measured},
            {'condition':'general','llm_request_count':1,**measured_usage([{'provider':'other','input_tokens':0,'output_tokens':0,'estimated_cost_usd':0}],1)}]
    group = aggregate_sessions(rows)['general']
    assert group['cost'] is None and group['cost_known_total'] == 0.125
    assert group['provider_usage']['priced']['estimated_cost_usd'] is None
    assert group['provider_usage']['priced']['estimated_cost_usd_known_total'] == 0.125
    assert group['provider_usage']['other']['requests'] is None
    assert group['provider_usage']['other']['requests_known_total'] == 1
    zero = aggregate_sessions([{'condition':'general','llm_request_count':0,**measured_usage([],0)}])['general']
    assert zero['cost'] == 0 and zero['llm_tokens'] == 0
