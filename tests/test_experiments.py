import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from uxagent.experiments import run_comparison


def test_comparison_preregisters_and_preserves_failed_denominator(tmp_path):
    personas = tmp_path / 'personas.jsonl'
    personas.write_text(Path('configs/persona.json').read_text(encoding='utf-8').replace('\n', '') + '\n', encoding='utf-8')
    observed = []
    async def fake_run(study, provider, persona, headed, output, *, persona_mode, run_id_override):
        manifest = json.loads(next((tmp_path / 'experiments').glob('*/experiment.json')).read_text(encoding='utf-8'))
        assert len(manifest['sessions']) == 4
        running = next(s for s in manifest['sessions'] if s['status'] == 'running')
        assert running['run_id'] == run_id_override
        assert Path(running['run_dir']).name == run_id_override
        observed.append(persona_mode)
        if len(observed) == 1:
            raise RuntimeError('private error text')
        return Path(output) / 'fake', {'run_id': str(len(observed)), 'verification': 'failure', 'termination_reason': 'max_steps', 'action_attempts': 2, 'elapsed_ms': 50, 'cost': None}
    with patch('uxagent.experiments.run_study', fake_run):
        directory, result = asyncio.run(run_comparison('configs/study.json', personas, repetitions=2, output_root=tmp_path))
    assert sorted(observed) == ['general', 'general', 'persona', 'persona']
    assert all(group['requested'] == 2 and group['rate'] == 0 for group in result['groups'].values())
    assert result['system_errors'] == 1
    assert len(result['sessions']) == 4
    assert 'private error text' not in (directory / 'experiment.json').read_text(encoding='utf-8')


def test_cancelled_comparison_keeps_unstarted_sessions(tmp_path):
    personas = tmp_path / 'personas.jsonl'
    personas.write_text(Path('configs/persona.json').read_text(encoding='utf-8').replace('\n', '') + '\n', encoding='utf-8')
    async def cancel(*args, **kwargs):
        raise asyncio.CancelledError()
    with patch('uxagent.experiments.run_study', cancel):
        try:
            asyncio.run(run_comparison('configs/study.json', personas, output_root=tmp_path))
        except asyncio.CancelledError:
            pass
    result = json.loads(next((tmp_path / 'experiments').glob('*/experiment.json')).read_text(encoding='utf-8'))
    assert len(result['sessions']) == 2
    assert sorted(s['status'] for s in result['sessions']) == ['cancelled', 'not_started']
    assert sum(group['requested'] for group in result['groups'].values()) == 2


def test_runner_preserves_action_when_post_observation_fails(tmp_path):
    from uxagent import runner
    study = tmp_path / 'study.json'
    raw = json.loads(Path('configs/study.json').read_text(encoding='utf-8'))
    raw['persona_file'] = str(Path('configs/persona.json').resolve())
    raw['action_timeout_ms'] = 15000
    study.write_text(json.dumps(raw), encoding='utf-8')
    original = runner.observe
    count = 0
    async def broken_observe(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError('post capture failed')
        return await original(*args, **kwargs)
    with patch('uxagent.runner.observe', broken_observe):
        directory, summary = asyncio.run(runner.run_study(study, headed=False, output_root=tmp_path / 'runs', persona_mode='general'))
    assert summary['termination_reason'] == 'browser_error'
    assert summary['metrics']['recording']['attempted'] == 1
    assert summary['metrics']['recording']['complete'] == 0
    assert summary['metrics']['recording']['rate'] == 0
    steps = [json.loads(line) for line in (directory / 'steps.jsonl').read_text(encoding='utf-8').splitlines()]
    assert steps[0]['action'] is not None
    assert steps[0]['next_observation_id'] is None
    general = json.loads((directory / 'persona.json').read_text(encoding='utf-8'))
    assert set(general) == {'constraints', 'intent', 'condition'}
    assert general['condition'] == 'general'

def test_comparison_persists_usage_and_missing_summary_fields(tmp_path):
    personas = tmp_path / 'personas.jsonl'
    personas.write_text(Path('configs/persona.json').read_text(encoding='utf-8').replace('\n', '') + '\n', encoding='utf-8')
    detail = {'provider':'mock','model':'fake','execution_mode':'ai','source_kind':'synthetic_fixture','llm_request_count':2,'llm_tokens':7,'provider_usage':{'mock':{'requests':2,'input_tokens':4,'output_tokens':3,'estimated_cost_usd':0}},'metrics':{'recording':{'complete':1,'attempted':2}}}
    async def fake_run(*args, **kwargs):
        return tmp_path / 'fake', {'run_id':kwargs['run_id_override'], 'verification':'success','termination_reason':'verified_success', **(detail if kwargs['persona_mode'] == 'general' else {})}
    with patch('uxagent.experiments.run_study', fake_run):
        directory, result = asyncio.run(run_comparison('configs/study.json', personas, output_root=tmp_path))
    saved = json.loads((directory / 'experiment.json').read_text(encoding='utf-8'))
    for session in saved['sessions']:
        for key, value in detail.items():
            assert session[key] == (value if session['condition'] == 'general' else None)
    assert result['groups']['general']['llm_request_count'] == 2
    assert result['groups']['persona']['llm_request_count'] is None


def test_dashboard_recomputes_legacy_groups_without_rewriting(tmp_path):
    from uxagent.monitor import Dashboard
    runs = tmp_path / 'runs'
    runs.mkdir()
    sessions = [{'condition':'general','status':'cancelled','verification':'unknown'}]
    path = runs / 'experiment.json'
    raw = json.dumps({'experiment_id':'legacy','sessions':sessions,'groups':{'general':{'rate':1}}})
    path.write_text(raw, encoding='utf-8')
    dashboard = Dashboard(runs, tmp_path / 'personas', Path('configs/study.json'))
    result = dashboard.experiments()[0]
    assert result['sessions'] == sessions
    assert result['groups']['general']['rate'] == 0
    assert result['groups']['general']['cost'] is None
    assert path.read_text(encoding='utf-8') == raw
