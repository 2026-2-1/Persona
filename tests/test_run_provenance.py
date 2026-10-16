"""New execution facts are explicit; old records are never inferred."""
import json
from pathlib import Path
import pytest
from uxagent.runner import run_study
from uxagent.schemas import StudyConfig
from uxagent.reports import build_cards

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_new_mock_run_records_execution_and_fixture_provenance(tmp_path):
    folder, _ = await run_study(ROOT/'configs/study.json', 'mock', headed=False, output_root=tmp_path)
    run = json.loads((folder/'run.json').read_text(encoding='utf-8'))
    assert run['execution_mode'] == 'ai'
    assert run['source_kind'] == 'synthetic_fixture'


def test_source_kind_is_an_explicit_validated_setting():
    raw = json.loads((ROOT/'configs/study.json').read_text(encoding='utf-8'))
    raw['source_kind'] = 'live_configured'
    assert StudyConfig.model_validate(raw).source_kind == 'live_configured'
    raw['source_kind'] = 'human_verified'
    with pytest.raises(ValueError):
        StudyConfig.model_validate(raw)


def test_legacy_provenance_remains_unknown():
    cards = build_cards({'run':{'run_id':'old','provider':'live'},'steps':[],
                        'summary':{'evaluator':{'feature_checks':[{'id':'f','label':'f','status':'fail'}]}}})
    assert cards[0]['execution_mode'] == cards[0]['source_kind'] == 'unknown'
