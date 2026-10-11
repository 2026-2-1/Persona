import json
from pathlib import Path
import pytest
from uxagent.llm import estimate_cost_usd
from uxagent.monitor import Dashboard
import uxagent.monitor as monitor
ROOT = Path(__file__).resolve().parents[1]

def test_alternative_model_cost_is_unknown():
    assert estimate_cost_usd('gemini', 100, 100, model='gemini-2.5-flash') is None
    assert estimate_cost_usd('gemini', 100, 100, model='gemini-2.5-flash-lite') > 0

def test_model_catalog_rejects_cross_provider_choice():
    from uxagent.model_catalog import resolve_model, catalog_payload
    assert resolve_model('live') == 'gpt-4o-mini'
    assert resolve_model('jev', 'gemini-2.5-flash') == 'gemini-2.5-flash'
    with pytest.raises(ValueError): resolve_model('live', 'gemini-2.5-flash')
    assert catalog_payload()['providers']['gemini']['default_model'] == 'gemini-2.5-flash-lite'

def test_connection_checks_selected_model(tmp_path, monkeypatch):
    dashboard=Dashboard(tmp_path/'runs',tmp_path/'personas',ROOT/'configs/study.json')
    seen=[]
    monkeypatch.setenv('OPENAI_API_KEY','prior-test-key')
    monkeypatch.setattr(dashboard,'_verify_connection',lambda provider,model=None: seen.append((provider,model)))
    result=dashboard.connect('live','test-key',model='gpt-4.1-mini')
    assert seen == [('live','gpt-4.1-mini')]
    assert result['model'] == 'gpt-4.1-mini'
    with pytest.raises(ValueError): dashboard.connect('live','test-key',model='wrong-model')
    assert len(seen)==1

def test_job_snapshot_preserves_selected_model(tmp_path,monkeypatch):
    class Process:
        def poll(self): return None
    commands=[]
    monkeypatch.setattr(monitor.subprocess,'Popen',lambda command,**kw:commands.append(command) or Process())
    monkeypatch.setenv('GEMINI_API_KEY','test-key')
    dashboard=Dashboard(tmp_path/'runs',tmp_path/'personas',ROOT/'configs/study.json')
    dashboard.personas_dir.mkdir()
    dashboard.personas_dir.joinpath('personas.jsonl').write_text((ROOT/'configs/persona.json').read_text(encoding='utf-8').replace('\n','')+'\n',encoding='utf-8')
    with pytest.raises(ValueError): dashboard.start_job('batch',provider='gemini',model='gpt-4.1-mini')
    assert not commands
    job=dashboard.start_job('batch',provider='gemini',model='gemini-2.5-flash')
    snapshot=json.loads(Path(commands[-1][commands[-1].index('--study')+1]).read_text(encoding='utf-8'))
    assert snapshot['provider_model']=='gemini-2.5-flash'
    assert job['model']=='gemini-2.5-flash'

@pytest.mark.asyncio
async def test_selected_model_reaches_request_and_all_run_artifacts(tmp_path,monkeypatch):
    import uxagent.runner as runner
    from uxagent.llm import GeminiProvider
    seen=[]
    async def complete(self,messages,model=None,temperature=.2,max_tokens=1200):
        seen.append(model)
        return json.dumps({'perception':'Observed','plan':'Stop','rationale_summary':'Test','action':None,'finish':{'claim':'give_up','summary':'Fake provider stop'}}), {'model':model,'input_tokens':20,'output_tokens':10}
    monkeypatch.setattr(runner,'load_env_file',lambda *args:None)
    monkeypatch.setattr(GeminiProvider,'complete',complete)
    config=json.loads((ROOT/'configs/study.json').read_text(encoding='utf-8'))
    config.update(provider_model='gemini-2.5-flash',persona_file=str(ROOT/'configs/persona.json'),headed=False)
    study=tmp_path/'study.json';study.write_text(json.dumps(config),encoding='utf-8')
    folder,summary=await runner.run_study(study,provider_name='gemini',output_root=tmp_path/'runs')
    assert seen==['gemini-2.5-flash']
    for name in ('run.json','summary.json'):
        assert json.loads((folder/name).read_text(encoding='utf-8'))['model']=='gemini-2.5-flash'
    calls=[json.loads(line) for line in (folder/'llm_calls.jsonl').read_text(encoding='utf-8').splitlines()]
    assert calls[0]['model']=='gemini-2.5-flash'
    assert calls[0]['provider']=='gemini'
    assert calls[0]['estimated_cost_usd'] is None

@pytest.mark.parametrize("legacy_model", ["gpt-4.1-mini","existing-custom-model"])
def test_dashboard_legacy_live_model_is_not_reset(tmp_path,monkeypatch,legacy_model):
    class Process:
        def poll(self): return None
    commands=[]
    monkeypatch.setattr(monitor.subprocess,'Popen',lambda command,**kw:commands.append(command) or Process())
    monkeypatch.setenv('OPENAI_API_KEY','test-key')
    config=json.loads((ROOT/'configs/study.json').read_text(encoding='utf-8'))
    config.update(model=legacy_model,persona_file=str(ROOT/'configs/persona.json'))
    study=tmp_path/'study.json';study.write_text(json.dumps(config),encoding='utf-8')
    dashboard=Dashboard(tmp_path/'runs',tmp_path/'personas',study)
    dashboard.personas_dir.mkdir()
    dashboard.personas_dir.joinpath('personas.jsonl').write_text((ROOT/'configs/persona.json').read_text(encoding='utf-8').replace('\n','')+'\n',encoding='utf-8')
    job=dashboard.start_job('batch',provider='live')
    snapshot=json.loads(Path(commands[-1][commands[-1].index('--study')+1]).read_text(encoding='utf-8'))
    assert snapshot['model']==legacy_model
    assert snapshot['provider_model']==('gpt-4.1-mini' if legacy_model=='gpt-4.1-mini' else None)
    assert job['model']==legacy_model
