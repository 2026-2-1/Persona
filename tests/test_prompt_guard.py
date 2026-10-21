"""Shared Qwen preflight: cover long history and every reduction request."""
import json

import pytest

from uxagent.llm import BudgetManager, BudgetExceeded, LocalQwenProvider
from uxagent.prompt_guard import PromptSizeError


@pytest.mark.asyncio
async def test_large_survey_reads_every_source_slice_and_preserves_questions_and_facts():
    provider = LocalQwenProvider()
    markers = [f'memory-{i:04d} 러닝화 가격과 실행 기록' for i in range(700)]
    form = {'questionnaire_id': 'q', 'questions': [{'id': 'q1', 'options': ['쉬웠다', '어려웠다']}]}
    facts = {'execution_trace': {'error_count': 2, 'failed_step_ids': [2, 5]}}
    messages = [{'role': 'system', 'content': 'Answer the three JSON lines using facts.'},
                {'role': 'user', 'content': '\n'.join(json.dumps(x, ensure_ascii=False)
                 for x in [form, [{'content': s} for s in markers], facts])}]
    sent, records = [], []

    async def enqueue(messages, model, temperature, max_tokens):
        sent.append(messages)
        payload = json.loads(messages[1]['content'])
        return json.dumps({'summary': f"조각 {payload['chunk_index']}의 기억을 요약했습니다."}), {
            'provider': 'gpu', 'model': model, 'input_tokens': 10, 'output_tokens': 10}

    provider._enqueue = enqueue
    budget = BudgetManager(None, None)
    prepared = await provider.prepare_messages(messages, 'persona-qwen', 512,
        budget=budget, call_log=records.append, module='survey', stage='questionnaire')
    chunks = [json.loads(m[1]['content'])['content'] for m in sent]
    assert all(marker in ''.join(chunks) for marker in markers)
    lines = [json.loads(s) for s in prepared[1]['content'].splitlines()]
    assert lines[0] == form and lines[2] == facts
    assert prepared[0] == messages[0]
    assert messages[1]['content'] != prepared[1]['content']  # originals untouched
    assert budget.requests == len(sent) == len(records) > 1
    assert all(r['stage'] == 'prompt_summary' for r in records)
    assert all(provider.prompt_guard.fits(m, 256) for m in sent)
    assert provider.prompt_guard.fits(prepared, 512)


@pytest.mark.asyncio
async def test_direct_provider_also_checks_long_context_before_dispatch():
    provider = LocalQwenProvider()
    seen = []

    async def enqueue(messages, model, temperature, max_tokens):
        assert provider.prompt_guard.fits(messages, max_tokens)
        seen.append(messages)
        if 'PROMPT_SUMMARY' in messages[0]['content']:
            return '{"summary":"관찰 핵심"}', {'input_tokens': 2, 'output_tokens': 2}
        return '{"ok":true}', {'input_tokens': 3, 'output_tokens': 3}

    provider._enqueue = enqueue
    messages = [{'role': 'system', 'content': 'Return JSON.'},
                {'role': 'user', 'content': json.dumps({'memories': ['가' * 500] * 50})}]
    raw, usage = await provider.complete(messages, 'persona-qwen', max_tokens=512)
    assert json.loads(raw) == {'ok': True}
    assert len(seen) > 1 and usage['prompt_guard']['checked'] is True


@pytest.mark.asyncio
async def test_summary_budget_is_enforced_before_any_hidden_request():
    provider = LocalQwenProvider()
    async def enqueue(*args):
        pytest.fail('an exhausted budget must not dispatch a summary')
    provider._enqueue = enqueue
    with pytest.raises(BudgetExceeded):
        await provider.prepare_messages([{'role': 'user', 'content': '가' * 15000}],
            'persona-qwen', 512, budget=BudgetManager(0, None))


@pytest.mark.asyncio
async def test_recursive_reduction_rechecks_summaries_until_merged_context_fits():
    provider = LocalQwenProvider()
    rounds = []
    async def enqueue(messages, model, temperature, max_tokens):
        assert provider.prompt_guard.fits(messages, max_tokens)
        payload = json.loads(messages[1]['content'])
        rounds.append(payload['round'])
        return json.dumps({'summary': '관찰된 실행 결과와 불확실성. ' * 12}), {
            'input_tokens': 10, 'output_tokens': 20}
    provider._enqueue = enqueue
    messages = [{'role': 'system', 'content': 'Return JSON.'},
                {'role': 'user', 'content': json.dumps({'memories': ['상품가' * 150] * 120}, ensure_ascii=False)}]
    prepared = await provider.prepare_messages(messages, 'persona-qwen', 512)
    assert max(rounds) >= 2
    assert provider.prompt_guard.fits(prepared, 512)


@pytest.mark.asyncio
async def test_overlarge_protected_contract_is_rejected_locally_without_summary_or_send():
    provider = LocalQwenProvider()
    async def enqueue(*args):
        pytest.fail('protected instructions/facts may not be silently summarized')
    provider._enqueue = enqueue
    for messages in [
        [{'role': 'system', 'content': '가' * 10000}],
        [{'role': 'user', 'content': json.dumps({'execution_trace': {'facts': '가' * 10000}})}],
    ]:
        with pytest.raises(PromptSizeError):
            await provider.complete(messages, 'persona-qwen', max_tokens=512)


@pytest.mark.asyncio
async def test_controls_and_persona_remain_exact_when_page_text_is_reduced():
    provider = LocalQwenProvider()
    controls = '<controls><control id="e3" role="textbox">상품 검색</control></controls>'
    navigation = '<navigation><control id="e9" path="러닝 &gt; 남성">남성</control></navigation>'
    source = '<page>' + navigation + '<visible_text>' + '러닝화 가격 ' * 4000 + '</visible_text>' + controls + '</page>'
    payload = {'persona': {'constraints': {'budget': 80000}}, 'intent': '러닝화 찾기',
               'valid_targets': {'inputs': ['e3'], 'clickable': ['e9']}, 'environment': source}
    async def enqueue(messages, model, temperature, max_tokens):
        return '{"summary":"러닝화와 가격이 보입니다."}', {'input_tokens': 3, 'output_tokens': 4}
    provider._enqueue = enqueue
    prepared = await provider.prepare_messages([{'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
                                                'persona-qwen', 512)
    result = json.loads(prepared[0]['content'])
    assert result['persona'] == payload['persona']
    assert result['valid_targets'] == payload['valid_targets']
    assert result['intent'] == payload['intent']
    assert controls in result['environment'] and navigation in result['environment']


@pytest.mark.asyncio
async def test_invalid_summary_is_logged_and_never_used_as_a_successful_observation():
    provider = LocalQwenProvider()
    records = []
    budget = BudgetManager(10, None)
    async def enqueue(*args):
        return '{"summary":', {'input_tokens': 4, 'output_tokens': 3}
    provider._enqueue = enqueue
    with pytest.raises(ValueError):
        await provider.prepare_messages([{'role': 'user', 'content': '가' * 10000}],
            'persona-qwen', 512, budget=budget, call_log=records.append)
    assert budget.reserved_tokens == 0 and budget.requests == 2
    assert len(records) == 2 and records[1]['repair_attempt'] == 1
    assert records[0]['error'] == 'JSONDecodeError'
    assert records[0]['response'] == '{"summary":'


@pytest.mark.asyncio
async def test_only_invalid_summary_slice_is_retried_once_with_a_shorter_contract():
    provider = LocalQwenProvider()
    records, requests = [], []
    async def enqueue(messages, model, temperature, max_tokens):
        requests.append(messages)
        return ('{"summary":' if len(requests) == 1 else '{"summary":"기록 요약"}'), {
            'input_tokens': 3, 'output_tokens': 3}
    provider._enqueue = enqueue
    result = await provider.prepare_messages([{'role': 'user', 'content': '가격 ' * 4000}],
        'persona-qwen', 512, call_log=records.append)
    assert requests[0][1] == requests[1][1]
    assert '80 characters' in requests[1][0]['content']
    assert provider.prompt_guard.fits(result, 512)
    assert records[0]['error'] == 'JSONDecodeError' and not records[1].get('error')


@pytest.mark.asyncio
async def test_matching_tokenizer_can_accept_payload_that_character_estimate_rejected():
    from uxagent.prompt_guard import PromptGuard
    class Counter:
        calls = 0
        def count(self, messages):
            self.calls += 1
            return {'prompt_tokens': 500, 'tokenizer_fingerprint': 'same-model'}
    counter = Counter()
    guard = PromptGuard(counter)
    messages = [{'role': 'system', 'content': '고정 지침' * 1500}]
    assert not guard.fits(messages, 512)
    await guard.inspect(messages, 512)
    assert guard.fits(messages, 512)
    assert guard.metadata(messages, 512)['exact_token_count'] is True
    await guard.inspect(messages, 512)
    assert counter.calls == 1


@pytest.mark.asyncio
async def test_counter_outage_does_not_silently_switch_to_an_estimate():
    from uxagent.prompt_guard import PromptGuard
    class Counter:
        def count(self, messages):
            raise RuntimeError('prompt_tokenizer_unavailable')
    guard = PromptGuard(Counter())
    with pytest.raises(RuntimeError, match='tokenizer_unavailable'):
        await guard.inspect([{'role': 'user', 'content': 'small'}], 512)


@pytest.mark.asyncio
async def test_oversized_protected_data_diagnostic_reports_sizes_without_content():
    provider = LocalQwenProvider()
    with pytest.raises(PromptSizeError) as error:
        await provider.prepare_messages([{'role': 'user', 'content': json.dumps({
            'task': 'PRIVATE_TASK' * 5000})}], 'persona-qwen', 512)
    assert 'user.task' in error.value.details['section_bytes']
    assert 'PRIVATE_TASK' not in str(error.value)
