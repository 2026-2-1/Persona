import json

from uxagent.reports import build_cards, export_report


def test_failed_feature_card_preserves_uncertainty_and_evidence():
    detail = {"run":{"run_id":"r1"}, "summary":{"evaluator":{"feature_checks":[
        {"id":"filters","label":"가격 필터","status":"fail","evidence":{"url":"https://shop.test"}}]}},
        "steps":[{"step_id":1,"observation_id":"obs-a","next_observation_id":"obs-b","action":None,"result":None}],
        "observations":{"obs-b":{"url":"https://shop.test"}},"config":{},"persona":{}}
    cards = build_cards(detail)
    assert cards[0]["review_status"] == "needs_human_review"
    assert cards[0]["evidence_step_ids"] == [1]
    assert "확정" not in cards[0]["hypothesis"]
    detail["cards"] = cards
    assert json.loads(export_report(detail, "json"))["cards"][0]["issue_id"] == cards[0]["issue_id"]
    assert "가격 필터" in export_report(detail, "md")


def test_report_escapes_page_text_and_removes_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-private-report-key")
    detail = {"run":{"run_id":"r"},"summary":{},"steps":[],"observations":{},
              "config":{"task":"<script>alert(1)</script> test-private-report-key"},"cards":[]}
    assert "<script>" not in export_report(detail,"html")
    for kind in ("html","md","json","csv"):
        assert "test-private-report-key" not in export_report(detail,kind)
