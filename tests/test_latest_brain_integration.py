import csv
import io
import json
from datetime import datetime, timezone

from uxagent.brain_trace import load_brain_trace
from uxagent.monitor import Dashboard
from uxagent.reports import export_report
from uxagent.schemas import BrainTaskEvent, WonderDrawRecord


def write_rows(folder, name, rows):
    (folder / name).write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                     for row in rows), encoding='utf-8')


def latest_folder(tmp_path):
    folder = tmp_path / 'latest-brain'
    folder.mkdir()
    (folder / 'run.json').write_text('{"run_id":"latest-brain","provider":"mock"}')
    now = datetime.now(timezone.utc)
    events = []
    for number, (task, kind, status) in enumerate([
        ('fast-1', 'perception', 'completed'),
        ('slow-1', 'reflection', 'completed'),
        ('slow-1', 'reflection', 'adopted'),
        ('slow-2', 'reflection', 'completed'),
        ('slow-2', 'reflection', 'discarded'),
    ]):
        events.append(BrainTaskEvent(
            event_id=f'event-{number}', task_id=task, run_id=folder.name,
            kind=kind, status=status, snapshot_seq=0,
            reason_code='stale_context' if status == 'discarded' else None,
            recorded_at=now,
        ).model_dump(mode='json'))
    write_rows(folder, 'brain_tasks.jsonl', events)
    draw = WonderDrawRecord(
        run_id=folder.name, seed=139, draw_index=1, parent_task_id='slow-1',
        parent_kind='reflection', roll=0.005, selected=True,
        wonder_task_id='wonder-1', recorded_at=now,
    ).model_dump(mode='json')
    write_rows(folder, 'wonder_draws.jsonl', [draw])
    return folder, events, draw


def test_current_schema_fast_and_consumption_events_are_not_dropped(tmp_path):
    folder, events, draw = latest_folder(tmp_path)
    brain = load_brain_trace(folder, folder.name)
    assert brain['warnings'] == []
    assert brain['task_events'] == events
    assert brain['task_counts']['adopted'] == 1
    assert brain['task_counts']['discarded'] == 1
    assert brain['task_counts']['completed'] == 1
    assert brain['wonder_draws'] == [draw]
    assert brain['wonder_seed_texts'] == ['139']


def test_detail_and_exports_share_the_validated_brain_records(tmp_path):
    folder, events, draw = latest_folder(tmp_path)
    write_rows(folder, 'brain_stages.jsonl', [
        {'run_id': folder.name, 'record_id': 'good', 'stage': 'reflection', 'text': '정상 생성'},
        {'run_id': 'other-run', 'record_id': 'foreign', 'stage': 'reflection', 'text': '다른 실행'},
    ])
    detail = Dashboard(tmp_path).run_detail(folder.name)
    assert detail['brain_stages'] == detail['brain']['stages']
    assert detail['brain_tasks'] == detail['brain']['task_events'] == events
    assert detail['wonder']['draws'] == detail['brain']['wonder_draws'] == [draw]
    assert '다른 실행' not in json.dumps(detail, ensure_ascii=False)
    output = json.loads(export_report(detail, 'json'))
    assert output['brain_tasks'] == output['brain']['task_events'] == events
    rows = list(csv.DictReader(io.StringIO(export_report(detail, 'csv'))))
    assert len([row for row in rows if row['record_type'] == 'brain_task_event']) == len(events)
    assert len([row for row in rows if row['record_type'] == 'wonder_draw']) == 1
    assert all(None not in row for row in rows)


def test_wonder_draw_symlinks_use_the_same_safe_reader(tmp_path):
    folder, _, _ = latest_folder(tmp_path)
    outside = tmp_path / 'outside.jsonl'
    outside.write_text('{"run_id":"latest-brain","draw_index":2}\n')
    (folder / 'wonder_draws.jsonl').unlink()
    (folder / 'wonder_draws.jsonl').symlink_to(outside)
    detail = Dashboard(tmp_path).run_detail(folder.name)
    assert detail['wonder']['draws'] == []
    assert any(row['file'] == 'wonder_draws.jsonl' and row['reason'] == 'unsafe_symlink'
               for row in detail['brain']['warnings'])
