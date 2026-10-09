from __future__ import annotations

import asyncio
import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .metrics import aggregate_sessions
from .runner import load_study, run_study
from .schemas import Persona
from .storage import write_json


async def run_comparison(study_path, personas_path, provider_name='mock', repetitions=1, output_root='runs'):
    if repetitions not in (1, 2, 3):
        raise ValueError('repetitions must be between 1 and 3')
    config, _, _ = load_study(study_path)
    if config.enable_slow_loop:
        raise ValueError('comparison requires slow loop disabled to keep the general condition persona-free')
    personas = [Persona.model_validate_json(line) for line in Path(personas_path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if not personas:
        raise ValueError('comparison requires at least one persona')
    if len({p.persona_id for p in personas}) != len(personas):
        raise ValueError('persona IDs must be unique')
    experiment_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    directory = Path(output_root) / 'experiments' / experiment_id
    directory.mkdir(parents=True, exist_ok=False)
    seed = int(uuid.uuid4().hex[:8], 16)
    sessions = [
        {'session_id': uuid.uuid4().hex, 'condition': condition, 'persona_id': p.persona_id if condition == 'persona' else None, 'pair_persona_id': p.persona_id,
         'repetition': repetition, 'status': 'not_started', 'verification': 'unknown', 'run_id': None, 'run_dir': None, 'cost': None}
        for p in personas for repetition in range(1, repetitions+1) for condition in ('general', 'persona')
    ]
    for session in sessions:
        session["run_id"] = experiment_id + "-" + session["session_id"][:12]
        session["run_dir"] = str((directory / "runs" / session["run_id"]).resolve())
    random.Random(seed).shuffle(sessions)
    result = {'schema_version': '1.0', 'experiment_id': experiment_id, 'study_id': config.study_id, 'started_at': datetime.now(timezone.utc).isoformat(),
              'settings': {'provider': provider_name, 'repetitions': repetitions, 'seed': seed, 'study': config.model_dump(), 'personas': [p.model_dump() for p in personas], 'prompt_version': 'fast-2', 'recovery_window_actions': 3},
              'sessions': sessions, 'system_errors': 0}
    def save():
        result['groups'] = aggregate_sessions(sessions)
        write_json(directory / 'experiment.json', result)
    save()
    by_id = {p.persona_id: p for p in personas}
    for session in sessions:
        session['status'] = 'running'
        save()
        try:
            run_dir, summary = await run_study(study_path, provider_name, by_id[session['pair_persona_id']], False, directory / 'runs', persona_mode=session['condition'], run_id_override=session['run_id'])
            session.update({key: summary.get(key) for key in ('run_id', 'verification', 'termination_reason', 'action_attempts', 'elapsed_ms', 'cost')})
            session['run_dir'] = str(run_dir.resolve())
            reason = summary.get('termination_reason')
            session['status'] = 'error' if reason in ('browser_error', 'model_error') else 'cancelled' if reason == 'interrupted' else 'completed'
            if session['status'] == 'error': result['system_errors'] += 1
        except (KeyboardInterrupt, asyncio.CancelledError):
            session.update(status="cancelled", verification="unknown", termination_reason="interrupted")
            save()
            raise
        except Exception as exc:
            session.update(status='error', verification='unknown', termination_reason='session_error', error={'code': type(exc).__name__, 'message': 'Session could not run; inspect local configuration and provider availability.'})
            result['system_errors'] += 1
        save()
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    save()
    return directory, result
