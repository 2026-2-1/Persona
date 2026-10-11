import asyncio
import json

import pytest

from uxagent.setup_guide import SetupGuide, static_options


class FakeProvider:
    def __init__(self, payload=None, error=None, usage=None):
        self.payload = payload or {"answer": "가정한 사용자 예시입니다.", "personas": [{"title": "빠른 비교", "background": "검색에 익숙하고 시간이 적은 사용자", "count": 2, "reason": "시간 제약 확인"}], "task_suggestion": None}
        self.error = error
        self.usage = usage or {"input_tokens": 100, "output_tokens": 100}
        self.calls = []

    async def complete(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self.error:
            raise RuntimeError(self.error)
        await asyncio.sleep(0)
        return json.dumps(self.payload), self.usage


def guide(fake):
    return SetupGuide(provider_factory=lambda provider: fake)


async def test_templates_are_free_and_explicit():
    fake = FakeProvider()
    result = await guide(fake).recommend("mock", None, "추천", {}, [])
    assert result["source"] == "template" and result["usage"]["requests"] == 0
    assert len(static_options()["scenarios"]) == 4
    assert len(result["personas"]) == 3 and not fake.calls


async def test_bounded_allowlist_context_history_and_valid_personas():
    fake = FakeProvider()
    result = await guide(fake).recommend("live", None, "추천", {"task": "상품 비교", "evaluator_success": "PRIVATE_ORACLE", "pages": "PRIVATE_PAGE"}, [{"role": "system", "content": "PRIVATE_SYSTEM"}] + [{"role": "user", "content": str(i)} for i in range(9)])
    sent = json.dumps(fake.calls[0][0])
    assert "PRIVATE_" not in sent
    assert len(fake.calls[0][0]) == 8
    assert fake.calls[0][1]["max_tokens"] == 1000
    assert result["source"] == "ai" and result["personas"][0]["count"] == 2
    assert result["usage"]["requests"] == 1


@pytest.mark.parametrize("location", ["message", "history", "context"])
async def test_environment_secret_blocked_before_send(monkeypatch, location):
    secret = "local-test-secret-value-123456"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    fake = FakeProvider()
    args = {"message": "추천", "context": {}, "history": []}
    args[location] = secret if location == "message" else ({"task": secret} if location == "context" else [{"role": "user", "content": secret}])
    with pytest.raises(ValueError, match="sensitive"):
        await guide(fake).recommend("live", None, **args)
    assert not fake.calls


async def test_url_credentials_blocked():
    fake = FakeProvider()
    with pytest.raises(ValueError):
        await guide(fake).recommend("live", None, "추천", {"target_url": "https://name:password@example.org"}, [])
    assert not fake.calls


@pytest.mark.parametrize("payload", [{"answer": "ok", "personas": [], "task_suggestion": None, "selector": "#submit"}, {"answer": "ok", "personas": [{"title": "t", "background": "b", "reason": "r", "count": "2"}], "task_suggestion": None}, {"answer": "sk-" + "x" * 30, "personas": [], "task_suggestion": None}])
async def test_unsafe_or_malformed_response_rejected(payload):
    with pytest.raises(ValueError, match="response"):
        await guide(FakeProvider(payload)).recommend("live", None, "추천", {}, [])


async def test_errors_count_without_leaking_details_or_retry():
    fake = FakeProvider(error="HTTP body private credential")
    service = guide(fake)
    for _ in range(5):
        with pytest.raises(RuntimeError, match="setup_guide_provider_failed"):
            await service.recommend("live", None, "추천", {}, [])
    with pytest.raises(RuntimeError, match="budget"):
        await service.recommend("live", None, "추천", {}, [])
    assert len(fake.calls) == 5


async def test_concurrent_requests_cannot_overspend_and_unknown_usage_is_null():
    fake = FakeProvider(usage={"model": "ignored"})
    service = guide(fake)
    results = await asyncio.gather(*(service.recommend("live", None, "추천", {}, []) for _ in range(9)), return_exceptions=True)
    valid = [r for r in results if isinstance(r, dict)]
    assert 1 <= len(valid) <= 5 and len(fake.calls) == len(valid)
    assert valid[0]["usage"]["input_tokens"] is None
    assert valid[0]["usage"]["estimated_cost_usd"] is None


async def test_environment_secret_in_output_is_rejected(monkeypatch):
    secret = "server-only-secret-for-output-test"
    monkeypatch.setenv("GEMINI_API_KEY", secret)
    fake = FakeProvider({"answer": secret, "personas": [], "task_suggestion": None})
    with pytest.raises(ValueError, match="invalid_response") as exc:
        await guide(fake).recommend("gemini", None, "추천", {}, [])
    assert secret not in str(exc.value)


async def test_jev_advice_uses_selected_gemini_and_reports_actual_provider():
    fake = FakeProvider()
    result = await guide(fake).recommend("jev", "gemini-2.5-flash", "추천", {}, [])
    assert result["provider"] == "gemini"
    assert result["model"] == fake.calls[0][1]["model"] == "gemini-2.5-flash"


async def test_large_multibyte_input_budget_blocks_before_provider():
    fake = FakeProvider()
    with pytest.raises(RuntimeError, match="budget"):
        await guide(fake).recommend("live", None, "한" * 1000, {"task": "한" * 1000, "persona_background": "한" * 1000}, [{"role": "user", "content": "한" * 500}] * 6)
    assert not fake.calls


async def test_new_gemini_model_price_is_unknown():
    result = await guide(FakeProvider()).recommend("gemini", "gemini-3.5-flash-lite", "추천", {}, [])
    assert result["usage"]["estimated_cost_usd"] is None


async def test_missing_server_key_does_not_spend_helper_budget(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = SetupGuide()
    with pytest.raises(ValueError, match="key_required"):
        await service.recommend("live", None, "추천", {}, [])
    assert service._budget.snapshot()["requests"] == 0


async def test_model_and_key_advice_receives_trusted_catalog_facts():
    fake = FakeProvider()
    await guide(fake).recommend("live", None, "모델과 키 발급 방법", {}, [])
    system = fake.calls[0][0][0]["content"]
    assert "gpt-4.1-mini" in system
    assert "https://platform.openai.com/api-keys" in system
    assert "ChatGPT 구독과 API" in system
    assert "Never invent" in system
    assert len(fake.calls) == 1


async def test_template_key_help_is_useful_without_api():
    fake = FakeProvider()
    result = await guide(fake).recommend("mock", None, "Claude API 키 발급 방법", {}, [])
    assert "https://console.anthropic.com/settings/keys" in result["answer"]
    assert "구독과 API" in result["answer"]
    assert result["personas"] == [] and not fake.calls


async def test_template_model_help_uses_catalog():
    result = await SetupGuide().recommend("scenario", None, "Gemini 모델 선택", {}, [])
    assert "gemini-3.5-flash-lite" in result["answer"]
    assert result["personas"] == []


@pytest.mark.parametrize("parameter", ["token", "access_token", "api_key", "session", "signature", "X-Amz-Signature"])
async def test_authenticated_query_url_not_sent(parameter):
    fake = FakeProvider()
    with pytest.raises(ValueError):
        await guide(fake).recommend("live", None, "추천", {"target_url": f"https://example.org/?{parameter}=tiny"}, [])
    assert not fake.calls


@pytest.mark.parametrize("field", ["message", "history", "task", "persona_background", "target_url"])
@pytest.mark.parametrize("suffix", ["?access_token=tiny", "#session=tiny", "?signature=tiny", "#/route?token=tiny"])
async def test_credential_urls_blocked_in_every_outbound_text(field, suffix):
    fake = FakeProvider()
    url = "https://example.org/" + suffix
    message, context, history = "추천", {}, []
    if field == "message":
        message = url
    elif field == "history":
        history = [{"role": "user", "content": url}]
    else:
        context[field] = url
    with pytest.raises(ValueError):
        await guide(fake).recommend("live", None, message, context, history)
    assert not fake.calls


async def test_json_unicode_encoded_secret_rejected_after_decode():
    class EscapedSecretProvider(FakeProvider):
        async def complete(self, messages, **kwargs):
            raw = json.dumps({"answer": "sk-" + "x" * 30, "personas": [], "task_suggestion": None})
            return raw.replace("sk-", r"\u0073k-"), {"input_tokens": 10, "output_tokens": 10}
    with pytest.raises(ValueError, match="invalid_response"):
        await guide(EscapedSecretProvider()).recommend("live", None, "추천", {}, [])


async def test_json_unicode_encoded_selector_rejected_after_decode():
    class EscapedSelectorProvider(FakeProvider):
        async def complete(self, messages, **kwargs):
            raw = json.dumps({"answer": "querySelector('#pay')", "personas": [], "task_suggestion": None})
            return raw.replace("querySelector", r"\u0071uerySelector"), {"input_tokens": 10, "output_tokens": 10}
    with pytest.raises(ValueError, match="invalid_response"):
        await guide(EscapedSelectorProvider()).recommend("live", None, "추천", {}, [])
