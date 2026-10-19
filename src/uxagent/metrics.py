from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import median


def _number(value):
    from math import isfinite
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0


def _count(value):
    return _number(value) and int(value) == value


def _coverage(values, name):
    valid = _number if name in ('cost', 'estimated_cost_usd') else _count
    known = [value for value in values if valid(value)]
    return {name: sum(known) if values and len(known) == len(values) else None,
            name + '_known_total': sum(known) if known else None,
            name + '_known_sessions': len(known),
            name + '_unknown_sessions': len(values) - len(known)}


def _usage_value(row, key):
    if not isinstance(row, dict):
        return None
    if row.get(key + '_complete') is False:
        return None
    if row.get(key + '_complete') is True:
        return row.get(key + '_measured_total')
    return row.get(key)


def _measured_coverage(rows, key):
    result = _coverage([_usage_value(row, key) for row in rows], key)
    subtotals = [row.get(key + '_measured_total') if key + '_measured_total' in row
                 else _usage_value(row, key) for row in rows if isinstance(row, dict)]
    valid = _number if key in ('cost', 'estimated_cost_usd') else _count
    known = [v for v in subtotals if valid(v)]
    result[key + '_known_total'] = sum(known) if known else None
    return result


def aggregate_sessions(sessions):
    groups = {}
    for condition in ('general', 'persona'):
        rows = [s for s in sessions if s.get('condition') == condition
                and s.get('execution_mode') != 'scripted' and s.get('provider') != 'scenario']
        successful = [s for s in rows if s.get('verification') == 'success']
        success = len(successful)
        def successful_median(key):
            values = [s.get(key) for s in successful if (_count if key == 'action_attempts' else _number)(s.get(key))]
            return median(values) if values else None
        group = {
            'requested': len(rows), 'success': success,
            'failure': sum(s.get('verification') == 'failure' for s in rows),
            'unknown': sum(s.get('verification') not in ('success', 'failure') for s in rows),
            'rate': success / len(rows) if rows else None,
            'median_actions': successful_median('action_attempts'),
            'median_ms': successful_median('elapsed_ms'),
            'median_population': 'verification_success',
            'median_actions_sessions': sum(_count(s.get('action_attempts')) for s in successful),
            'median_ms_sessions': sum(_number(s.get('elapsed_ms')) for s in successful),
            'statuses': {status: sum((s.get('status') or 'unknown') == status for s in rows)
                         for status in sorted({(s.get('status') or 'unknown') for s in rows})},
        }
        for name in ('cost', 'llm_request_count', 'llm_tokens'):
            group.update(_measured_coverage(rows, name) if name in ('llm_tokens', 'cost') else _coverage([_usage_value(s, name) for s in rows], name))
        # A present mapping enumerates the providers used; a missing mapping cannot
        # establish zero usage. An empty mapping with nonzero requests is incomplete.
        usages = [s.get('provider_usage') if isinstance(s.get('provider_usage'), dict)
                  and (s['provider_usage'] or (_count(s.get('llm_request_count')) and s.get('llm_request_count') == 0)) else None for s in rows]
        providers = sorted({name for usage in usages if usage is not None for name in usage})
        group['provider_usage'] = {}
        for provider in providers:
            entry = {}
            for key in ('requests', 'input_tokens', 'output_tokens', 'estimated_cost_usd'):
                provider_rows = [
                    usage[provider] if usage is not None and provider in usage
                    else {key: 0} if usage is not None and row.get('provider_usage_complete') is not False else {}
                    for row, usage in zip(rows, usages)]
                entry.update(_measured_coverage(provider_rows, key))
            group['provider_usage'][provider] = entry
        for key in ('input_tokens', 'output_tokens'):
            values = []
            for usage in usages:
                parts = [_usage_value(entry, key) for entry in usage.values()] if usage is not None else None
                values.append(sum(parts) if parts is not None and all(_count(v) for v in parts) else None)
            group.update(_coverage(values, key))
            subtotals = [entry.get(key + '_measured_total') if key + '_measured_total' in entry else _usage_value(entry, key)
                         for usage in usages if usage is not None for entry in usage.values() if isinstance(entry, dict)]
            known = [v for v in subtotals if _count(v)]
            if known:
                group[key + '_known_total'] = sum(known)
        recordings = []
        for row in rows:
            metrics = row.get('metrics')
            recording = metrics.get('recording') if isinstance(metrics, dict) else None
            if not isinstance(recording, dict) or not _count(recording.get('attempted')) or not _count(recording.get('complete')) or recording['complete'] > recording['attempted']:
                recording = None
            recordings.append(recording)
        recording = {}
        for key in ('complete', 'attempted'):
            recording.update(_coverage([r.get(key) if r else None for r in recordings], key))
        recording['known_sessions'] = sum(r is not None for r in recordings)
        recording['unknown_sessions'] = len(rows) - recording['known_sessions']
        recording['rate'] = recording['complete'] / recording['attempted'] if recording['attempted'] else None
        recording['known_rate'] = recording['complete_known_total'] / recording['attempted_known_total'] if recording['attempted_known_total'] else None
        group['recording'] = recording
        groups[condition] = group
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
