import json
from datetime import datetime, timezone

import pytest
from playwright.sync_api import expect, sync_playwright

from uxagent.schemas import WonderDrawRecord
from test_brain_trace import brain_folder
from test_brain_trace_browser import trace_dashboard
from test_review_export_browser import download_reports


@pytest.mark.parametrize('seed', [7930736020609184225, 2**63 - 1])
def test_large_wonder_seed_matches_screen_and_all_exports(
        trace_dashboard, brain_folder, tmp_path, seed):
    draw = WonderDrawRecord(
        run_id=brain_folder.name, seed=seed, draw_index=1,
        parent_task_id='tcompleted', parent_kind='reflection',
        roll=0.5, selected=False, recorded_at=datetime.now(timezone.utc))
    path = brain_folder / 'wonder_draws.jsonl'
    path.write_text(draw.model_dump_json() + '\n', encoding='utf-8')
    original = path.read_bytes()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(accept_downloads=True)
        page.goto(trace_dashboard)
        page.locator('#tab-history').click()
        page.locator('#brain-trace > summary').click()
        page.locator('[data-brain-key="wonder"] > summary').click()
        expect(page.locator('[data-brain-key="wonder"] li')).to_contain_text(
            'seed ' + str(seed))
        reports = download_reports(page, tmp_path)
        exported = json.loads(reports['json'])['brain']
        assert exported['wonder_draws'] == [draw.model_dump(mode='json')]
        assert exported['wonder_seed_texts'] == [str(seed)]
        for kind in ('csv', 'md', 'html'):
            assert str(seed) in reports[kind]
        browser.close()
    assert path.read_bytes() == original
