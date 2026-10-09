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
