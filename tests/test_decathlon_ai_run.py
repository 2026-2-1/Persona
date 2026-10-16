import json
from pathlib import Path

import pytest

import uxagent.runner as runner_module
from uxagent.runner import run_study

ROOT = Path(__file__).resolve().parents[1]


def _study(tmp_path):
    raw = json.loads((ROOT / "configs/study-decathlon.json").read_text(encoding="utf-8"))
    raw["persona_file"] = str(ROOT / "configs/persona.json")
    study = tmp_path / "study.json"
    study.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return study


def _provider_opening(product):
    class DetailProvider:
        clicked = False

        async def complete(self, messages, *args, **kwargs):
            usage = {"model": "fake", "input_tokens": 1, "output_tokens": 1}
            stage = messages[0]["content"].split("FAST_STAGE:", 1)[1].splitlines()[0]
            if stage == "perception":
                return json.dumps({"perception": "상품 목록"}, ensure_ascii=False), usage
            if stage == "plan":
                return json.dumps({"plan": "상세 열기"}, ensure_ascii=False), usage
            obs = json.loads(messages[-1]["content"])["observation"]
            if DetailProvider.clicked:
                return json.dumps({"rationale_summary": "상세를 열었다", "action": None,
                                   "finish": {"claim": "completed", "summary": "상세 확인"}},
                                  ensure_ascii=False), usage
            target = next(e for e in obs["clickable_elements"] if e["name"] == product + " 상세 보기")
            DetailProvider.clicked = True
            return json.dumps({"rationale_summary": "상품 확인",
                               "action": {"type": "click", "observation_id": obs["observation_id"],
                                          "tab_id": obs["tab_id"], "target_id": target["id"]}, "finish": None},
                              ensure_ascii=False), usage
    return DetailProvider


@pytest.mark.asyncio
async def test_decathlon_ai_run_succeeds_only_on_matching_detail(monkeypatch, tmp_path):
    monkeypatch.setattr(runner_module, "MockProvider", _provider_opening("러닝 가방 블랙"))
    _, summary = await run_study(_study(tmp_path), "mock", None, False, tmp_path / "match")
    assert summary["termination_reason"] == "verified_success"
    assert summary["verification"] == "success"


@pytest.mark.asyncio
@pytest.mark.parametrize("product", ["러닝 가방 블루", "러닝 가방 프로", "트레킹 신발 블랙"])
async def test_decathlon_ai_run_rejects_detail_outside_task_conditions(monkeypatch, tmp_path, product):
    # Without expectations, decathlon-detail-v1 passed any product whose seven detail fields were shown.
    monkeypatch.setattr(runner_module, "MockProvider", _provider_opening(product))
    _, summary = await run_study(_study(tmp_path), "mock", None, False, tmp_path / "mismatch")
    assert summary["termination_reason"] == "agent_finished"
    assert summary["verification"] == "failure"


def test_decathlon_study_keeps_expected_answer_out_of_task_prompt():
    raw = json.loads((ROOT / "configs/study-decathlon.json").read_text(encoding="utf-8"))
    assert raw["evaluation_expectations"]["product_name"] not in raw["task"]
