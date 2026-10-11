"""Local append-only human review history; locks coordinate all stores in this process."""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schemas import CandidateReviewInput, CandidateReviewRecord
from .setup_guide import _check_sensitive

_locks = {}
_locks_guard = threading.Lock()


class ReviewError(ValueError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.status = status


class ReviewStore:
    def __init__(self, root):
        self.root = Path(root).absolute()

    def _path(self, folder):
        folder = Path(folder).absolute()
        path = folder / 'candidate_reviews.jsonl'
        if not folder.is_relative_to(self.root):
            raise ReviewError('unsafe_review_path')
        # Inspect lexical ancestors before resolving, including the configured root.
        if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in (path, *path.parents)):
            raise ReviewError('unsafe_review_path')
        if not folder.is_dir() or (path.exists() and not path.is_file()):
            raise ReviewError('unsafe_review_path')
        return path

    def _lock(self, path):
        key = os.path.normcase(str(path.resolve()))
        with _locks_guard:
            return _locks.setdefault(key, threading.RLock())

    def read(self, folder, run_id):
        path = self._path(folder)
        with self._lock(path):
            if not path.exists():
                return []
            try:
                text = path.read_text(encoding='utf-8')
                if text and not text.endswith('\n'):
                    raise ValueError()
                rows = []
                for line in text.splitlines():
                    row = CandidateReviewRecord.model_validate(json.loads(line)).model_dump()
                    if row['run_id'] != run_id:
                        raise ValueError()
                    _check_sensitive(row)
                    rows.append(row)
                return rows
            except (ValueError, OSError) as exc:
                raise ReviewError('review_history_unavailable', 500) from None

    def append(self, folder, run_id, payload, cards, completed):
        try:
            value = CandidateReviewInput.model_validate(payload)
            _check_sensitive(value.model_dump())
        except ValueError:
            raise ReviewError('invalid_review_input') from None
        path = self._path(folder)
        with self._lock(path):
            self.read(folder, run_id)
            if not completed:
                raise ReviewError('run_active', 409)
            card = next((c for c in cards if c['card_id'] == value.card_id), None)
            if card is None:
                raise ReviewError('card_not_found', 404)
            if card['card_version'] != value.card_version:
                raise ReviewError('card_version_conflict', 409)
            row = CandidateReviewRecord(**value.model_dump(), run_id=run_id,
                review_id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc).isoformat()).model_dump()
            with path.open('a', encoding='utf-8', newline='\n') as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + '\n')
                handle.flush()
                os.fsync(handle.fileno())
            return row


def overlay_reviews(cards, history):
    summary = dict.fromkeys(('total','reviewed','deferred','unreviewed','valid','invalid','tool_error','environment_error'), 0)
    result = []
    for original in cards:
        matching = [r for r in history if r['card_id'] == original['card_id'] and r['card_version'] == original['card_version']]
        latest = matching[-1] if matching else None
        status = ('deferred' if latest['verdict'] == 'deferred' else 'reviewed') if latest else 'needs_human_review'
        result.append({**original, 'review_history':matching, 'latest_review':latest,
            'review_status':status, 'verdict':latest['verdict'] if latest else None,
            'note':latest['note'] if latest else '', 'reviewer_id':latest['reviewer_id'] if latest else None})
        summary['total'] += 1
        summary['unreviewed' if latest is None else status] += 1
        if latest and latest['verdict'] != 'deferred':
            summary[latest['verdict']] += 1
    return result, summary
