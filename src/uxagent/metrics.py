from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import median


def aggregate_sessions(sessions):
    groups = {}
    for condition in ('general', 'persona'):
        rows = [s for s in sessions if s['condition'] == condition]
        costs = [s.get('cost') for s in rows]
        successful = [s for s in rows if s.get('verification') == 'success']
        success = sum(s.get('verification') == 'success' for s in rows)
        groups[condition] = {
            'requested': len(rows), 'success': success,
            'failure': sum(s.get('verification') == 'failure' for s in rows),
            'unknown': sum(s.get('verification', 'unknown') == 'unknown' for s in rows),
            'rate': success / len(rows) if rows else None,
            'median_actions': median([s['action_attempts'] for s in successful if s.get('action_attempts') is not None]) if any(s.get('action_attempts') is not None for s in successful) else None,
            'median_ms': median([s['elapsed_ms'] for s in successful if s.get('elapsed_ms') is not None]) if any(s.get('elapsed_ms') is not None for s in successful) else None,
            'median_population': 'verified_success',
            'cost': sum(costs) if costs and all(c is not None for c in costs) else None,
            'statuses': {status: sum(s['status'] == status for s in rows) for status in sorted({s['status'] for s in rows})},
        }
    return groups


def run_metrics(run_dir, steps, recoverable_codes=('action_timeout',), recovery_window=3, *, attempted_count=None):
    run_dir = Path(run_dir)
    actions = [s for s in steps if s.get('action') is not None]
    attempted = max(len(actions), attempted_count if attempted_count is not None else len(actions))
    unrecorded = attempted - len(actions)
    missing = []
    for step in actions:
        absent = []
        result = step.get('result')
        if not isinstance(result, dict) or not isinstance(result.get('ok'), bool):
            absent.append('result')
        action_ms = (step.get('timing_ms') or {}).get('action')
        if not isinstance(action_ms, (int, float)) or isinstance(action_ms, bool) or action_ms < 0:
            absent.append('action_timing')
        for phase in ('pre', 'post'):
            try:
                datetime.fromisoformat(step.get(f'{phase}_observed_at', ''))
            except (ValueError, TypeError):
                absent.append(f'{phase}_time')
        for phase, key in (('pre', 'observation_id'), ('post', 'next_observation_id')):
            identifier = step.get(key)
            path = run_dir / 'observations' / f'{identifier}.json'
            if not identifier or not path.is_file():
                absent.append(f'{phase}_json')
                absent.append(f'{phase}_png')
                continue
            try:
                observation = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(observation.get('url'), str) or not observation['url']:
                    absent.append(f'{phase}_url')
                capture = observation.get('capture', {})
                screenshot = capture.get('screenshot_path')
                if not screenshot or not (run_dir / screenshot).is_file():
                    absent.append(f'{phase}_png')
            except (ValueError, OSError):
                absent.extend((f'{phase}_json', f'{phase}_png'))
        if absent:
            missing.append({'step_id': step.get('step_id'), 'missing': absent})
    episodes = []
    active = None
    for index, step in enumerate(actions):
        result = step.get('result') or {}
        code = (result.get('error') or {}).get('code')
        if code in recoverable_codes and active is None:
            active = {'start_step': step.get('step_id'), 'start_index': index, 'error_code': code, 'recovered': False, 'additional_actions': None}
            episodes.append(active)
        elif active is not None and result.get('ok'):
            active['additional_actions'] = index - active['start_index']
            active['recovered'] = active['additional_actions'] <= recovery_window
            active = None
    recovered = sum(e['recovered'] for e in episodes)
    return {
        'recording': {'attempted': attempted, 'complete': len(actions)-len(missing), 'rate': (len(actions)-len(missing))/attempted if attempted else None, 'unrecorded': unrecorded, 'missing': missing},
        'recovery': {'window_actions': recovery_window, 'recoverable_codes': list(recoverable_codes), 'episodes': episodes, 'recovered': recovered, 'rate': recovered/len(episodes) if episodes else None, 'method': 'first successful tool action after a recoverable error; does not imply task success'},
    }
