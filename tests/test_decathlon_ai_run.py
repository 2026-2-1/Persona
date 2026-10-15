import json
from pathlib import Path

import pytest

import uxagent.runner as runner_module
from uxagent.runner import run_study

ROOT = Path(__file__).resolve().parents[1]


def _study(tmp_path):
    raw = {
        "study_id": "decathlon-synthetic-ai-v1",
        "start_url": "http://127.0.0.1:8000/decathlon.html",
        "task": "가방을 검색해 검정색이면서 3만원 이하인 상품을 찾고 상세 정보를 확인하세요.",
        "allowed_origins": ["http://127.0.0.1:8000"],
        "persona_file": str(ROOT / "configs/persona.json"),
        "evaluator_id": "decathlon-detail-v1",
        "evaluation_expectations": {"product_name": "러닝 가방 블랙", "color": "검정", "max_price": 30000},
        "max_steps": 3,
        "run_timeout_seconds": 30,
    }
    study = tmp_path / "study.json"
    study.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return study


def _provider_opening(product):
    class DetailProvider:
        model = "mock-v1"
        clicked = False

        async def complete(self, messages, *args, **kwargs):
            stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0] if "FAST_STAGE:" in messages[0]["content"] else None
            payload = json.loads(messages[-1]["content"])
            usage = {"model": "mock-v1", "input_tokens": 1, "output_tokens": 1}
            if stage == "perception":
                return json.dumps({"perception": "상품 목록 또는 상세 화면입니다."}, ensure_ascii=False), usage
            if stage == "plan":
                return json.dumps({"plan": "상품 상세를 확인합니다."}, ensure_ascii=False), usage
            if stage == "decision":
                obs = payload["observation"]
                target = next((e for e in obs["clickable_elements"] if e["name"] == product + " 상세 보기"), None)
                if target and not DetailProvider.clicked:
                    DetailProvider.clicked = True
                    decision = {"rationale_summary": "상품 상세를 엽니다.", "action": {
                        "type": "click", "observation_id": obs["observation_id"],
                        "tab_id": obs["tab_id"], "target_id": target["id"]}, "finish": None}
                else:
                    decision = {"rationale_summary": "상세를 확인했습니다.", "action": None,
                                "finish": {"claim": "completed", "summary": "상세 확인"}}
                return json.dumps(decision, ensure_ascii=False), usage
            if "Rate the importance of one memory" in messages[0]["content"]:
                return json.dumps({"score": 5, "reason": "상품 확인 기억"}, ensure_ascii=False), usage
            if "Summarize up to three brief insights" in messages[0]["content"]:
                return json.dumps({"insights": [], "next_focus": "상세 확인"}, ensure_ascii=False), usage
            if "Review whether the supplied plan" in messages[0]["content"]:
                return json.dumps({"review": "계획 유지", "suggested_revisions": []}, ensure_ascii=False), usage
            return json.dumps({"thought": "차 한잔"}, ensure_ascii=False), usage
    return DetailProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("product,expected", [
    ("러닝 가방 블랙", "success"),
    ("러닝 가방 블루", "failure"),
    ("러닝 가방 프로", "failure"),
])
async def test_staged_ai_run_uses_independent_decathlon_expectations(monkeypatch, tmp_path, product, expected):
    monkeypatch.setattr(runner_module, "MockProvider", _provider_opening(product))
    _, summary = await run_study(_study(tmp_path), "mock", None, False, tmp_path / "runs")
    assert summary["verification"] == expected
    assert summary["termination_reason"] == ("verified_success" if expected == "success" else "agent_finished")


def test_decathlon_study_keeps_expected_answer_out_of_task_prompt():
    raw = json.loads((ROOT / "configs/study-decathlon.json").read_text(encoding="utf-8"))
    assert raw["evaluation_expectations"]["product_name"] not in raw["task"]


@pytest.mark.asyncio
async def test_runner_passes_configured_evaluation_profile(monkeypatch, tmp_path):
    profile = json.loads((ROOT / "configs/decathlon_profile.json").read_text(encoding="utf-8"))
    profile["selectors"]["detail"] = "#missing-detail"
    (tmp_path / "broken_profile.json").write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    study = _study(tmp_path)
    raw = json.loads(study.read_text(encoding="utf-8"))
    raw["evaluation_profile_file"] = "broken_profile.json"
    study.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(runner_module, "MockProvider", _provider_opening("러닝 가방 블랙"))
    _, summary = await run_study(study, "mock", None, False, tmp_path / "profile")
    assert summary["verification"] != "success"
    assert summary["evaluator"]["reason"] == "detail_evidence_unavailable"


def test_live_decathlon_study_uses_public_profile_without_fixed_answer():
    raw = json.loads((ROOT / "configs/study-decathlon-live.json").read_text(encoding="utf-8"))
    assert raw["evaluator_id"] == "decathlon-detail_basic-v1"
    assert raw["evaluation_profile_file"] == "decathlon_live_profile.json"
    assert "product_name" not in raw["evaluation_expectations"]
    assert raw["evaluation_expectations"]["product_name_contains"] in raw["task"]
