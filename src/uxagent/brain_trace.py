"""Read optional Brain logs without turning generated content into evaluation."""
from __future__ import annotations

import json
from pathlib import Path
from .schemas import WonderDrawRecord

TASK_STATES = ('scheduled', 'started', 'completed', 'adopted', 'discarded', 'skipped', 'failed', 'cancelled')
STAGES = ('perception', 'plan', 'decision', 'importance', 'reflection', 'plan_review', 'wonder')
KINDS = STAGES


def _read(folder, name, run_id, identity, versions, warnings):
    path = folder / name
    if path.is_symlink():
        warnings.append({'file': name, 'reason': 'unsafe_symlink'})
        return []
    if not path.exists():
        return []
    rows = []
    try:
        with path.open(encoding='utf-8') as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict) or row.get('run_id') != run_id:
                        raise ValueError('invalid_identity')
                    if name == 'wonder_draws.jsonl':
                        WonderDrawRecord.model_validate(row)
                    elif not isinstance(row.get(identity), str) or not row[identity]:
                        raise ValueError('missing_id')
                    if row.get('schema_version', '1.0') not in versions:
                        raise ValueError('unsupported_schema')
                    if name == 'brain_stages.jsonl' and (row.get('stage') not in STAGES or not isinstance(row.get('text'), str)):
                        raise ValueError('invalid_stage')
                    if name == 'brain_tasks.jsonl' and (row.get('status') not in TASK_STATES or row.get('kind') not in KINDS):
                        raise ValueError('invalid_task')
                    if name == 'memory_changes.jsonl' and row.get('change') not in ('importance_scored', 'evicted'):
                        raise ValueError('invalid_change')
                    # Lists are consumed as references, never as executable instructions.
                    for key in ('source_memory_ids', 'output_record_ids'):
                        if key in row and (not isinstance(row[key], list) or any(not isinstance(x, str) for x in row[key])):
                            raise ValueError('invalid_references')
                    rows.append(row)
                except (json.JSONDecodeError, ValueError):
                    warnings.append({'file': name, 'line': line_number, 'reason': 'invalid_record'})
    except (OSError, UnicodeError):
        warnings.append({'file': name, 'reason': 'unreadable_log'})
    return rows


def load_brain_trace(folder: Path, run_id: str):
    warnings = []
    stages = _read(folder, 'brain_stages.jsonl', run_id, 'record_id', ('1.0',), warnings)
    events = _read(folder, 'brain_tasks.jsonl', run_id, 'event_id', ('1.0',), warnings)
    originals = _read(folder, 'memory.jsonl', run_id, 'memory_id', ('1.0', '2.0'), warnings)
    changes = _read(folder, 'memory_changes.jsonl', run_id, 'event_id', ('1.0',), warnings)
    draws = _read(folder, 'wonder_draws.jsonl', run_id, 'draw_index', ('1.0',), warnings)
    latest = {}
    for event in events:
        task_id = event.get('task_id')
        if isinstance(task_id, str) and task_id:
            latest[task_id] = event
        else:
            warnings.append({'file': 'brain_tasks.jsonl', 'reason': 'missing_task_id'})
    memories = {row['memory_id']: {**row, 'evicted': False,
                'importance_scale': '1–10' if row.get('schema_version') == '2.0' else '0–5'} for row in originals}
    for event in changes:
        memory = memories.get(event.get('memory_id'))
        if memory is None:
            warnings.append({'file': 'memory_changes.jsonl', 'reason': 'missing_source_memory'})
            continue
        if event['change'] == 'evicted':
            memory['evicted'] = True
            memory['eviction_reason'] = event.get('reason_code')
        elif isinstance(event.get('importance_after'), int) and not isinstance(event['importance_after'], bool) and 1 <= event['importance_after'] <= 10:
            memory['importance'] = event['importance_after']
            memory['importance_scale'] = '1–10'
        else:
            warnings.append({'file': 'memory_changes.jsonl', 'reason': 'invalid_importance'})
    return {'available': any((folder / name).exists() or (folder / name).is_symlink() for name in
                            ('brain_stages.jsonl', 'brain_tasks.jsonl', 'memory_changes.jsonl', 'wonder_draws.jsonl')),
            'stages': stages, 'task_events': events, 'tasks': list(latest.values()),
            'task_counts': {state: sum(t['status'] == state for t in latest.values()) for state in TASK_STATES},
            'memories': list(memories.values()), 'memory_changes': changes,
            'wonder_draws': draws, 'warnings': warnings}
