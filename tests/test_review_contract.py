import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from uxagent import schemas, reports


def review_input(**changes):
    value = dict(card_id="feature-search", card_version="a" * 64,
                 reviewer_id="reviewer-1", verdict="valid", note="확인함")
    value.update(changes)
    return value


def detail():
    return {"run": {"run_id": "run-1", "execution_mode": "scripted", "source_kind": "synthetic_fixture"},
            "steps": [{"step_id": 1, "observation_id": "obs-1", "action": {"type": "click"}, "result": {"ok": True}}],
            "summary": {"verification": "failure", "evaluator": {"feature_checks": [
                {"id": "search", "label": "검색", "status": "fail", "step_id": 1, "evidence": {"found": False}}]}}}


def test_review_input_contract_exists_and_accepts_each_verdict():
    assert hasattr(schemas, "CandidateReviewInput")
    for verdict in ("valid", "invalid", "deferred", "tool_error", "environment_error"):
        assert schemas.CandidateReviewInput(**review_input(verdict=verdict)).verdict == verdict


@pytest.mark.parametrize("changes", [
    {"run_id": "client-run"}, {"reviewer_id": " "}, {"card_id": "\t"},
    {"verdict": "needs_human_review"}, {"note": "x" * 4001},
    {"reviewer_id": "x" * 201}, {"card_version": "a" * 63}, {"card_id": 1},
    {"card_id": "x" * 201}, {"card_version": "A" * 64},
])
def test_review_input_rejects_invalid_values(changes):
    assert hasattr(schemas, "CandidateReviewInput")
    with pytest.raises(ValidationError):
        schemas.CandidateReviewInput(**review_input(**changes))


def test_review_record_preserves_server_fields():
    assert hasattr(schemas, "CandidateReviewRecord")
    record = schemas.CandidateReviewRecord(**review_input(), schema_version="1.0", run_id="run-1",
        review_id="926f9f45-9f2c-430b-a6d1-f65ff5240548", created_at="2026-10-11T01:00:00Z")
    assert record.model_dump()["run_id"] == "run-1"
    with pytest.raises(ValidationError):
        schemas.CandidateReviewRecord(**{**record.model_dump(), "created_at": "2026-10-11T01:00:00"})


def test_review_text_is_normalized():
    assert hasattr(schemas, "CandidateReviewInput")
    value = schemas.CandidateReviewInput(**review_input(reviewer_id=" reviewer-1 ", note=" \t "))
    assert value.reviewer_id == "reviewer-1"
    assert value.note == ""


def test_cards_have_stable_identity_and_factual_version():
    source = detail()
    card = reports.build_cards(source)[0]
    assert card.get("card_id") == card["issue_id"]
    assert len(card["card_version"]) == 64
    assert card["run_id"] == "run-1"
    assert reports.build_cards(copy.deepcopy(source))[0]["card_version"] == card["card_version"]
    source["steps"][0]["result"]["ok"] = False
    assert reports.build_cards(source)[0]["card_version"] != card["card_version"]
    source = detail()
    source["summary"]["evaluator"]["feature_checks"][0]["evidence"]["found"] = True
    assert reports.build_cards(source)[0]["card_version"] != card["card_version"]


def test_review_overlay_and_dictionary_order_do_not_change_version():
    assert hasattr(reports, "enrich_card_identity")
    card = reports.build_cards(detail())[0]
    changed = dict(reversed(list(card.items())))
    changed.update(review_status="reviewed", verdict="valid", note="검토", reviewer_id="human",
                   created_at="later", review_history=[{"verdict": "valid"}], latest_review={"note": "검토"})
    assert reports.enrich_card_identity(changed, detail())["card_version"] == card["card_version"]


def test_legacy_source_is_unknown_and_success_creates_no_candidates():
    source = detail()
    source["run"] = {"run_id": "run-1"}
    card = reports.build_cards(source)[0]
    assert card.get("execution_mode") == "unknown"
    assert card.get("source_kind") == "unknown"
    source["summary"]["evaluator"]["feature_checks"][0]["status"] = "pass"
    assert reports.build_cards(source) == []


def test_documented_examples_match_card_versions_and_record_schema():
    examples = json.loads((Path(__file__).parents[1] / "docs/examples/c-review-contract.json").read_text(encoding="utf-8"))
    for example in examples["examples"]:
        assert reports.build_cards(example["detail"]) == example["cards"]
        if "review_record" in example:
            schemas.CandidateReviewRecord.model_validate(example["review_record"])


@pytest.mark.parametrize("check_id", [" 검색 조건 ", "가" * 100, "line\nbreak"])
def test_review_accepts_existing_evaluation_check_identity_exactly(check_id):
    schemas.EvaluationCheck(id=check_id, label="조건", kind="url_contains", expected="search")
    source = detail()
    source["summary"]["evaluator"]["feature_checks"][0]["id"] = check_id
    card = reports.build_cards(source)[0]
    value = schemas.CandidateReviewInput(**review_input(card_id=card["card_id"]))
    assert value.card_id == "feature-" + check_id


@pytest.mark.parametrize("observation_id, field", [("obs-1", "html"), ("obs-2", "url")])
def test_linked_observation_fact_changes_invalidate_card_version(observation_id, field):
    source = detail()
    source["steps"][0]["next_observation_id"] = "obs-2"
    source["observations"] = {"obs-1": {"url": "https://example.test/", "html": "가격 없음"},
                              "obs-2": {"url": "https://example.test/search", "html": "결과 없음"}}
    before = reports.build_cards(source)[0]["card_version"]
    source["observations"][observation_id][field] += "changed"
    assert reports.build_cards(source)[0]["card_version"] != before


def test_linked_observation_display_urls_do_not_change_version():
    source = detail()
    source["observations"] = {"obs-1": {"url": "https://example.test/", "html": "가격 없음",
        "screenshot_url": "/artifacts/run-1/observations/obs-1.png",
        "capture": {"screenshot_path": "runs/run-1/observations/obs-1.png", "truncated": False}}}
    before = reports.build_cards(source)[0]["card_version"]
    source["observations"]["obs-1"]["screenshot_url"] = "/artifacts/moved/observations/obs-1.png"
    source["observations"]["obs-1"]["capture"]["screenshot_path"] = "moved/obs-1.png"
    assert reports.build_cards(source)[0]["card_version"] == before
