import csv
import io
import json
from pathlib import Path
import pytest
from uxagent.monitor import Dashboard
from uxagent.reports import export_report


def write_rows(folder,name,rows):
    (folder/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')


@pytest.fixture
def brain_folder(tmp_path):
    folder=tmp_path/'runs'/'brain-demo';folder.mkdir(parents=True)
    (folder/'run.json').write_text(json.dumps({'run_id':'brain-demo','execution_mode':'ai','source_kind':'synthetic_fixture'}))
    (folder/'summary.json').write_text(json.dumps({'verification':'unknown'}))
    write_rows(folder,'memory.jsonl',[{'schema_version':'2.0','run_id':'brain-demo','memory_id':'m1','seq':1,'kind':'observation','text':'원본 관찰','importance':None,'source_observation_ids':['obs-memory-source'],'source_step_ids':[6],'source_stage_record_id':'stage1'}])
    write_rows(folder,'brain_stages.jsonl',[{'schema_version':'1.0','run_id':'brain-demo','record_id':'stage1','stage':'reflection',
        'text':'<script>AI 가상 성찰</script>','source_memory_ids':['m1'],'snapshot_seq':1,'content_status':'generated'}])
    write_rows(folder,'brain_tasks.jsonl',[{'schema_version':'1.0','run_id':'brain-demo','event_id':'e'+str(i),'task_id':'t'+status,
        'kind':'reflection','status':status,'source_memory_ids':['m1'],'output_record_ids':['stage1'] if status=='completed' else []}
        for i,status in enumerate(('scheduled','started','completed','skipped','failed','cancelled'))])
    write_rows(folder,'memory_changes.jsonl',[{'schema_version':'1.0','run_id':'brain-demo','event_id':'c1','memory_id':'m1','change':'importance_scored','importance_after':9},
        {'schema_version':'1.0','run_id':'brain-demo','event_id':'c2','memory_id':'m1','change':'evicted','reason_code':'active_limit'}])
    return folder


def test_trace_keeps_task_states_and_evicted_original_memory(brain_folder):
    detail=Dashboard(brain_folder.parent).run_detail(brain_folder.name)
    trace=detail['brain']
    assert trace['available']
    assert set(trace['task_counts'])=={'scheduled','started','completed','skipped','failed','cancelled'}
    assert all(v==1 for v in trace['task_counts'].values())
    memory=trace['memories'][0]
    assert memory['text']=='원본 관찰' and memory['importance']==9 and memory['evicted']
    assert detail['summary']['verification']=='unknown'
    for kind in ('json','csv','md','html'):
        output=export_report(detail,kind)
        assert 'stage1' in output and 'm1' in output
    assert '<script>AI 가상 성찰</script>' not in export_report(detail,'html')
    rows=list(csv.DictReader(io.StringIO(export_report(detail,'csv'))))
    assert any(r['record_type']=='brain_stage' and json.loads(r['brain_record'])['record_id']=='stage1' for r in rows)


def test_latest_task_status_uses_append_order_not_time(brain_folder):
    with (brain_folder/'brain_tasks.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({'schema_version':'1.0','run_id':'brain-demo','event_id':'new','task_id':'tscheduled','kind':'reflection','status':'failed','recorded_at':'1900-01-01T00:00:00Z'})+'\n')
    trace=Dashboard(brain_folder.parent).run_detail(brain_folder.name)['brain']
    assert trace['task_counts']['scheduled']==0 and trace['task_counts']['failed']==2


def test_invalid_cross_run_and_symlink_trace_are_reported(brain_folder,tmp_path):
    with (brain_folder/'brain_stages.jsonl').open('a',encoding='utf-8') as f:
        f.write('broken\n'+json.dumps({'schema_version':'1.0','run_id':'another','record_id':'foreign','stage':'plan','text':'foreign'})+'\n')
    external=tmp_path/'external.jsonl';external.write_text('{}\n')
    (brain_folder/'memory_changes.jsonl').unlink()
    (brain_folder/'memory_changes.jsonl').symlink_to(external)
    trace=Dashboard(brain_folder.parent).run_detail(brain_folder.name)['brain']
    assert len(trace['stages'])==1
    assert len(trace['warnings'])==3
    assert trace['memories'][0]['importance'] is None


def test_legacy_without_brain_files_is_readable(tmp_path):
    folder=tmp_path/'old';folder.mkdir()
    (folder/'run.json').write_text('{"run_id":"old"}')
    detail=Dashboard(tmp_path).run_detail('old')
    assert not detail['brain']['available']
    assert detail['brain']['stages']==[]
    assert 'brain_record' not in export_report(detail,'csv')


def test_brain_text_is_redacted_in_api_and_every_export(brain_folder,monkeypatch):
    secret='test-provider-secret-not-a-real-key'
    monkeypatch.setenv('OPENAI_API_KEY',secret)
    with (brain_folder/'brain_stages.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({'schema_version':'1.0','run_id':'brain-demo','record_id':'secret-stage','stage':'reflection','text':secret})+'\n')
    detail=Dashboard(brain_folder.parent).run_detail(brain_folder.name)
    assert secret not in json.dumps(detail)
    for kind in ('json','csv','md','html'):
        assert secret not in export_report(detail,kind)
