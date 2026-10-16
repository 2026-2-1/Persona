import json
from uxagent.metrics import run_metrics


def test_evidence_completeness_requires_both_observations(tmp_path):
    folder = tmp_path / 'observations'
    folder.mkdir()
    for identifier in ('before', 'after'):
        (folder / f'{identifier}.json').write_text(json.dumps({'capture': {'screenshot_path': f'observations/{identifier}.png'}}))
    (folder / 'before.png').write_bytes(b'png')
    steps = [{'action': {'type': 'click'}, 'observation_id': 'before', 'next_observation_id': 'after', 'result': {'ok': True}}]
    metrics = run_metrics(tmp_path, steps)
    assert metrics['recording']['attempted'] == 1
    assert metrics['recording']['complete'] == 0
    assert metrics['recording']['rate'] == 0
    assert metrics['recovery']['rate'] is None


def test_recovery_distinguishes_tool_recovery_from_task_success(tmp_path):
    steps = [
        {'step_id': 1, 'action': {'type': 'click'}, 'result': {'ok': False, 'error': {'code': 'action_timeout'}}},
        {'step_id': 2, 'action': {'type': 'click'}, 'result': {'ok': False, 'error': {'code': 'action_timeout'}}},
        {'step_id': 3, 'action': {'type': 'click'}, 'result': {'ok': True}},
    ]
    recovery = run_metrics(tmp_path, steps)['recovery']
    assert len(recovery['episodes']) == 1
    assert recovery['rate'] == 1
    assert recovery['episodes'][0]['additional_actions'] == 2


def test_complete_evidence_requires_urls_result_and_capture_times(tmp_path):
    folder = tmp_path / 'observations'
    folder.mkdir()
    for identifier in ('before', 'after'):
        (folder / f'{identifier}.json').write_text(json.dumps({'url': 'https://example.test', 'capture': {'screenshot_path': f'observations/{identifier}.png'}}))
        (folder / f'{identifier}.png').write_bytes(b'png')
    step = {'step_id': 1, 'action': {'type': 'click'}, 'observation_id': 'before', 'next_observation_id': 'after', 'result': {'ok': True}, 'timing_ms': {'action': 1}, 'pre_observed_at': '2026-10-09T00:00:00+00:00', 'post_observed_at': '2026-10-09T00:00:01+00:00'}
    assert run_metrics(tmp_path, [step])['recording']['rate'] == 1
    for key in ('result', 'timing_ms', 'pre_observed_at', 'post_observed_at'):
        incomplete = {k: v for k, v in step.items() if k != key}
        assert run_metrics(tmp_path, [incomplete])['recording']['complete'] == 0
    (folder / 'after.json').write_text(json.dumps({'capture': {'screenshot_path': 'observations/after.png'}}))
    assert 'post_url' in run_metrics(tmp_path, [step])['recording']['missing'][0]['missing']


def test_medians_use_only_independently_successful_sessions():
    from uxagent.metrics import aggregate_sessions
    sessions = [
        {'condition': 'general', 'status': 'completed', 'verification': 'success', 'action_attempts': 4, 'elapsed_ms': 100, 'cost': 0},
        {'condition': 'general', 'status': 'completed', 'verification': 'failure', 'action_attempts': 30, 'elapsed_ms': 5000, 'cost': 0},
        {'condition': 'persona', 'status': 'completed', 'verification': 'unknown', 'action_attempts': 10, 'elapsed_ms': 200, 'cost': None},
    ]
    groups = aggregate_sessions(sessions)
    assert groups['general']['median_actions'] == 4
    assert groups['general']['median_ms'] == 100
    assert groups['persona']['median_actions'] is None
    assert groups['general']['median_population'] == 'verified_success'


def test_unrecorded_attempt_is_kept_in_recording_denominator(tmp_path):
    recording = run_metrics(tmp_path, [], attempted_count=1)['recording']
    assert recording['attempted'] == 1
    assert recording['complete'] == 0
    assert recording['rate'] == 0
    assert recording['unrecorded'] == 1

def test_planned_coverage_excludes_scripted_and_keeps_unknowns():
    from uxagent.metrics import aggregate_sessions
    rows = [{'condition': 'general', 'status': status, 'verification': 'success' if i < 2 else 'unknown', 'cost': 0 if i == 0 else None} for i, status in enumerate(['completed', 'completed', 'error', 'cancelled', 'not_started'])]
    rows += [{'condition':'general','status':'completed','verification':'success','execution_mode':'scripted'}, {'condition':'general','status':'completed','verification':'success','provider':'scenario'}]
    group = aggregate_sessions(rows)['general']
    assert group['requested'] == 5 and group['success'] == 2 and group['rate'] == .4
    assert group['cost'] is None and group['cost_known_total'] == 0
    assert group['cost_known_sessions'] == 1 and group['cost_unknown_sessions'] == 4
    assert group['recording']['attempted'] is None
    assert aggregate_sessions([])['general']['rate'] is None
    assert aggregate_sessions(rows[2:5])['general']['rate'] == 0


def test_usage_and_recording_partial_coverage_and_invalid_numbers():
    from uxagent.metrics import aggregate_sessions
    rows = [
        {'condition':'persona','status':'completed','verification':'success','cost':True,'action_attempts':float('inf'),'llm_request_count':2,'llm_tokens':10,'provider_usage':{'mock':{'requests':2,'input_tokens':8,'output_tokens':None,'estimated_cost_usd':0}},'metrics':{'recording':{'attempted':2,'complete':1}}},
        {'condition':'persona','status':'error','verification':'unknown','cost':-1,'llm_request_count':None,'provider_usage':{'mock':{'requests':1,'input_tokens':None,'output_tokens':3,'estimated_cost_usd':None}}},
    ]
    group = aggregate_sessions(rows)['persona']
    assert group['median_actions'] is None
    assert group['cost_known_sessions'] == 0
    assert group['llm_request_count'] is None and group['llm_request_count_known_total'] == 2
    assert group['input_tokens'] is None and group['input_tokens_known_total'] == 8
    assert group['output_tokens'] is None and group['output_tokens_known_total'] == 3
    assert group['provider_usage']['mock']['requests'] == 3
    assert group['provider_usage']['mock']['input_tokens_unknown_sessions'] == 1
    assert group['recording']['rate'] is None and group['recording']['known_rate'] == .5
    assert group['recording']['unknown_sessions'] == 1

def test_count_values_and_null_status_and_median_coverage():
    from uxagent.metrics import aggregate_sessions
    rows = [{'condition':'general','status':None,'verification':'success','action_attempts':2,'elapsed_ms':1.5,'llm_request_count':.5,'llm_tokens':True,'provider_usage':{'mock':{'requests':.5,'input_tokens':.5,'output_tokens':2}},'metrics':{'recording':{'attempted':.5,'complete':0}}}, {'condition':'general','status':'completed','verification':'success'}]
    group = aggregate_sessions(rows)['general']
    assert group['statuses'] == {'unknown':1,'completed':1}
    assert group['llm_request_count_known_sessions'] == 0
    assert group['input_tokens_known_sessions'] == 0
    assert group['recording']['known_sessions'] == 0
    assert group['median_actions_sessions'] == 1 and group['median_ms_sessions'] == 1


def test_empty_usage_nonzero_requests_remains_unknown():
    from uxagent.metrics import aggregate_sessions
    group = aggregate_sessions([{'condition':'general','status':'completed','provider_usage':{},'llm_request_count':1}])['general']
    assert group['input_tokens'] is None and group['output_tokens'] is None

def test_empty_usage_boolean_request_count_does_not_establish_zero():
    from uxagent.metrics import aggregate_sessions
    group = aggregate_sessions([{'condition':'general','status':'completed','provider_usage':{},'llm_request_count':False}])['general']
    assert group['llm_request_count'] is None
    assert group['input_tokens'] is None and group['output_tokens'] is None
    assert group['input_tokens_known_sessions'] == 0
