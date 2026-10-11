import pytest
from uxagent.candidate_reviews import ReviewStore, overlay_reviews

def test_append_restart_and_overlay(tmp_path):
    store = ReviewStore(tmp_path)
    run = tmp_path / 'r1'; run.mkdir()
    card = {'card_id':'한글/opaque', 'card_version':'a'*64,'review_status':'needs_human_review'}
    data = dict(card_id=card['card_id'],card_version=card['card_version'],reviewer_id='human',verdict='valid',note='checked')
    first = store.append(run,'r1',data,[card],True)
    second = store.append(run,'r1',{**data,'verdict':'deferred'},[card],True)
    history = ReviewStore(tmp_path).read(run,'r1')
    assert history == [first,second]
    cards, summary = overlay_reviews([card],history)
    assert cards[0]['latest_review'] == second
    assert summary['deferred'] == 1 and summary['reviewed'] == 0
    changed, counts = overlay_reviews([{**card,'card_version':'b'*64}],history)
    assert changed[0]['review_history'] == [] and counts['unreviewed'] == 1
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uxagent.monitor import Dashboard, make_handler
from uxagent.candidate_reviews import ReviewError
from uxagent.reports import export_report

def fixture_run(tmp_path):
    run=tmp_path/'nested'/'r1'; run.mkdir(parents=True)
    (run/'run.json').write_text(json.dumps({'run_id':'r1','execution_mode':'scripted'}))
    (run/'summary.json').write_text(json.dumps({'verification':'failure','evaluator':{'feature_checks':[{'id':'점검/a','label':'check','status':'fail'}]}}))
    return run

def test_concurrent_stores_corruption_and_sensitive(tmp_path, monkeypatch):
    run=tmp_path/'r1';run.mkdir()
    card={'card_id':'x','card_version':'a'*64}
    data=dict(card_id='x',card_version='a'*64,reviewer_id='human',verdict='valid')
    def save(_): return ReviewStore(tmp_path).append(run,'r1',data,[card],True)
    with ThreadPoolExecutor(max_workers=8) as pool: records=list(pool.map(save,range(24)))
    assert len(ReviewStore(tmp_path).read(run,'r1'))==24
    assert len({r['review_id'] for r in records})==24
    monkeypatch.setenv('DEMO_SECRET','private-secret-value')
    for payload in ({**data,'note':'private-secret-value'},{**data,'reviewer_id':'https://x.test/?token=abcdefghi'},{**data,'verdict':'oops'}):
        with pytest.raises(ReviewError,match='invalid_review_input'): save_store=ReviewStore(tmp_path).append(run,'r1',payload,[card],True)
    (run/'candidate_reviews.jsonl').write_text('{broken}\n')
    with pytest.raises(ReviewError,match='review_history_unavailable'): ReviewStore(tmp_path).read(run,'r1')
    with pytest.raises(ReviewError): save(0)
    assert (run/'candidate_reviews.jsonl').read_text()=='{broken}\n'

def test_http_restart_errors_and_exports(tmp_path):
    run=fixture_run(tmp_path)
    dashboard=Dashboard(tmp_path)
    server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(dashboard))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    def request(path,payload=None,origin=None):
        headers={'Content-Type':'application/json'}
        if origin: headers['Origin']=origin
        req=Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        try:
            with urlopen(req) as response:return response.status,response.read().decode()
        except HTTPError as error:return error.code,error.read().decode()
    try:
        code,body=request('/api/reviews/r1');assert code==200
        card=json.loads(body)['cards'][0]
        payload=dict(card_id=card['card_id'],card_version=card['card_version'],reviewer_id='=reviewer',verdict='tool_error',note='<script>note</script>')
        assert request('/api/reviews/r1',payload,'https://evil.test')[0]==403
        assert request('/api/reviews/missing',payload)[0]==404
        assert request('/api/reviews/r1',{**payload,'card_id':'missing'})[0]==404
        assert request('/api/reviews/r1',{**payload,'card_version':'b'*64})[0]==409
        code,body=request('/api/reviews/r1',{**payload,'verdict':'secret-invalid-verdict'});assert code==400 and 'secret-invalid-verdict' not in body
        assert request('/api/reviews/r1',payload)[0]==201
        detail=Dashboard(tmp_path).run_detail('r1')
        assert detail['summary']['verification']=='failure'
        assert detail['review_summary']['tool_error']==1 and detail['review_summary']['reviewed']==1
        for kind in ('json','csv','md','html'):
            code,body=request('/api/export/r1?format='+kind);assert code==200
            assert 'tool_error' in body and 'reviewed' in body and 'note' in body
            if kind=='html': assert '<script>' not in body
            if kind=='csv': assert "'=reviewer" in body
        (run/'summary.json').unlink()
        assert request('/api/reviews/r1',payload)[0]==409
        (run/'candidate_reviews.jsonl').write_text('{broken}\n')
        assert request('/api/reviews/r1')[0]==500
        assert request('/api/reviews/r1',payload)[0]==500
    finally:
        server.shutdown();server.server_close();thread.join()

def test_symlink_file_and_ancestor_rejected(tmp_path):
    run=tmp_path/'r1';run.mkdir();target=tmp_path/'target';target.write_text('')
    try: (run/'candidate_reviews.jsonl').symlink_to(target)
    except OSError: pytest.skip('symlink creation unavailable')
    with pytest.raises(ReviewError): ReviewStore(tmp_path).read(run,'r1')
    (run/'candidate_reviews.jsonl').unlink()
    alias=tmp_path/'alias';alias.symlink_to(run,target_is_directory=True)
    with pytest.raises(ReviewError): ReviewStore(tmp_path).read(alias,'r1')

def test_wrong_metadata_identity_and_legacy(tmp_path):
    run=fixture_run(tmp_path);dashboard=Dashboard(tmp_path)
    (run/'run.json').write_text('{}')
    card=dashboard.run_detail('r1')['cards'][0]
    assert card['run_id']=='r1'
    payload=dict(card_id=card['card_id'],card_version=card['card_version'],reviewer_id='human',verdict='valid')
    dashboard.append_review('r1',payload)
    (run/'run.json').write_text(json.dumps({'run_id':'wrong'}))
    with pytest.raises(ReviewError,match='run_identity_conflict'): dashboard.append_review('r1',payload)
@pytest.mark.parametrize('verdict', ['valid','invalid','deferred','tool_error','environment_error'])
def test_all_verdicts_export_identical_state(tmp_path,verdict):
    fixture_run(tmp_path);dashboard=Dashboard(tmp_path)
    card=dashboard.run_detail('r1')['cards'][0]
    row=dashboard.append_review('r1',dict(card_id=card['card_id'],card_version=card['card_version'],reviewer_id='reviewer',verdict=verdict,note='memo'))
    detail=dashboard.run_detail('r1');state='deferred' if verdict=='deferred' else 'reviewed'
    assert detail['cards'][0]['review_status']==state
    for kind in ('json','csv','md','html'):
        report=export_report(detail,kind)
        assert state in report and verdict in report and 'memo' in report and row['review_id'] in report

def test_metadata_symlink_write_rejected(tmp_path):
    run=fixture_run(tmp_path);dashboard=Dashboard(tmp_path)
    card=dashboard.run_detail('r1')['cards'][0]
    original=run/'run.json';target=tmp_path/'metadata';target.write_text(original.read_text());original.unlink()
    try: original.symlink_to(target)
    except OSError: pytest.skip('symlink creation unavailable')
    with pytest.raises(ReviewError,match='unsafe_review_path'):
        dashboard.append_review('r1',dict(card_id=card['card_id'],card_version=card['card_version'],reviewer_id='human',verdict='valid'))
@pytest.mark.parametrize('secret', ['quote"credential', 'slash\\credential', 'line\ncredential'])
@pytest.mark.parametrize('field', ['note', 'reviewer_id'])
def test_json_escaped_environment_secrets_rejected_before_persistence(tmp_path,monkeypatch,secret,field):
    monkeypatch.setenv('REVIEW_TEST_SECRET',secret)
    run=tmp_path/'r1';run.mkdir()
    card={'card_id':'x','card_version':'a'*64}
    payload=dict(card_id='x',card_version='a'*64,reviewer_id='reviewer',verdict='valid',note='memo')
    payload[field]='before '+secret+' after'
    with pytest.raises(ReviewError,match='invalid_review_input'):
        ReviewStore(tmp_path).append(run,'r1',payload,[card],True)
    assert not (run/'candidate_reviews.jsonl').exists()

@pytest.mark.parametrize('secret', ['quote"credential', 'slash\\credential', 'line\ncredential'])
def test_stored_escaped_environment_secrets_fail_closed(tmp_path,monkeypatch,secret):
    run=tmp_path/'r1';run.mkdir()
    card={'card_id':'x','card_version':'a'*64}
    payload=dict(card_id='x',card_version='a'*64,reviewer_id='reviewer',verdict='valid',note='before '+secret+' after')
    ReviewStore(tmp_path).append(run,'r1',payload,[card],True)
    monkeypatch.setenv('REVIEW_TEST_SECRET',secret)
    with pytest.raises(ReviewError,match='review_history_unavailable'):
        ReviewStore(tmp_path).read(run,'r1')
