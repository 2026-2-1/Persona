import json

import pytest

from uxagent.model_json import loads_action_json


@pytest.mark.parametrize('literal, expected', [('false', False), ('true', True)])
def test_observed_qwen_enter_boolean_typo_is_parsed_without_changing_action_values(literal, expected):
    raw = ('{"actions":[{"action":"type","target":"s22","text":"80000",'
           '"enter=' + literal + '","description":"최대 가격 입력"}]}')
    parsed, repaired = loads_action_json(raw)
    assert repaired is True
    assert parsed == {"actions": [{"action": "type", "target": "s22", "text": "80000",
                                   "enter": expected, "description": "최대 가격 입력"}]}


def test_valid_json_with_enter_equals_in_text_is_not_changed():
    raw = '{"actions":[{"action":"type","description":"enter=false","enter":false}]}'
    parsed, repaired = loads_action_json(raw)
    assert repaired is False
    assert parsed["actions"][0]["description"] == "enter=false"


def test_unrelated_json_error_remains_an_error():
    with pytest.raises(json.JSONDecodeError):
        loads_action_json('{"actions":[{"action":"type","target":"s22","text":}]}')


def test_complete_plan_values_with_only_root_object_close_missing_are_recovered():
    from uxagent.model_json import loads_model_json
    from uxagent.schemas import UPlan

    raw = '{"plan":"필터 상태 확인","rationale":"상한 적용 여부 확인","next_step":"최대 가격 확인"\n'
    repairs = []
    result = loads_model_json(raw, repairs=repairs)
    assert UPlan.model_validate(result).next_step == '최대 가격 확인'
    assert repairs == ['root_object_close']


def test_root_closing_scan_preserves_braces_and_escaped_quotes_inside_strings():
    from uxagent.model_json import loads_model_json
    value = {'text': '중괄호 } 와 배열 [ 및 "인용"', 'nested': {'items': ['가격']}}
    assert loads_model_json(json.dumps(value, ensure_ascii=False)[:-1]) == value


@pytest.mark.parametrize('raw', ['{"plan":"잘린 문장', '{"plan":["완결 문장"', '{"plan":{"text":"문장"', '{"plan":800'])
def test_root_close_recovery_never_completes_unfinished_values_or_nested_containers(raw):
    from uxagent.model_json import loads_model_json
    with pytest.raises(json.JSONDecodeError):
        loads_model_json(raw)


@pytest.mark.parametrize('raw, expected, rule', [
    ('\ufeff{"ok":true}', {'ok': True}, 'bom'),
    ('```json\n{"ok":true}\n```', {'ok': True}, 'json_fence'),
    ('{"items":[1,2,],}', {'items': [1, 2]}, 'trailing_comma'),
    ('{"ok":True,"no":False,"empty":None}', {'ok': True, 'no': False, 'empty': None}, 'python_literal'),
    ('{"value"=42}', {'value': 42}, 'equals_separator'),
    ('{value:42}', {'value': 42}, 'unquoted_key'),
    ('{"text":"첫 줄\n둘째 줄\t탭"}', {'text': '첫 줄\n둘째 줄\t탭'}, 'string_control_character'),
    ('{"a":"x" "b":2}', {'a': 'x', 'b': 2}, 'missing_comma'),
    ('{"a":5 "b":2}', {'a': 5, 'b': 2}, 'missing_comma'),
    ('[{"a":1}{"b":2}]', [{'a': 1}, {'b': 2}], 'missing_comma'),
    ('{"a" "x"}', {'a': 'x'}, 'missing_colon'),
])
def test_common_model_syntax_errors_are_checked_without_changing_values(raw, expected, rule):
    from uxagent.model_json import loads_model_json
    repairs = []
    assert loads_model_json(raw, repairs=repairs) == expected
    assert rule in repairs


@pytest.mark.parametrize('raw', [
    '{"text":"unfinished', '{"text":}', '{"n":1', '{"ok":tru}',
    '{"a":1} {"a":2}', 'answer: {"a":1}', '{"a":1,"a":2}',
    '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}',
    '["a""b"]',
    '{"actions":[{"target":"s1","target":"s2"}]}',
])
def test_ambiguous_truncated_duplicate_or_nonfinite_json_is_rejected(raw):
    from uxagent.model_json import loads_model_json
    with pytest.raises(json.JSONDecodeError):
        loads_model_json(raw)


def test_normal_json_preserves_quoted_syntax_and_escapes_exactly():
    from uxagent.model_json import loads_model_json
    value = {'text': 'True False None enter=false, } ```json\n검색', 'path': r'C:\temp\new', 'n': 1.5}
    repairs = []
    assert loads_model_json(json.dumps(value, ensure_ascii=False), repairs=repairs) == value
    assert repairs == []


def test_transport_json_is_strict_and_outbound_nonfinite_numbers_are_rejected():
    from uxagent.model_json import loads_json, dumps_json, loads_transport_json, ProviderJSONError
    with pytest.raises(json.JSONDecodeError):
        loads_json('{"ok":True,}')
    with pytest.raises(ValueError):
        dumps_json({'bad': float('nan')})
    with pytest.raises(ProviderJSONError):
        loads_transport_json('[]')


def test_large_number_of_syntax_errors_stops_at_the_repair_limit():
    from uxagent.model_json import loads_model_json
    raw = '{' + ','.join(f'field{i}:1' for i in range(40)) + '}'
    repairs = []
    with pytest.raises(json.JSONDecodeError, match='repair limit'):
        loads_model_json(raw, repairs=repairs)
    assert len(repairs) == 32


@pytest.mark.asyncio
@pytest.mark.parametrize('module, stage, raw, schema', [
    ('fast', 'perception', '```json\n{"observations":["관찰"],}\n```', 'UPerception'),
    ('fast', 'feedback', '{thoughts:["생각"],}', 'UFeedback'),
    ('fast', 'plan', '{"plan":"계획","rationale":"이유","next_step":"다음",}', 'UPlan'),
    ('fast', 'plan', '{"plan":"계획","rationale":"이유","next_step":"다음"', 'UPlan'),
    ('fast', 'decision', '{"actions":[{"action":"terminate","description":"끝",}],}', 'UActions'),
    ('slow', 'reflection', '{"insights":["성찰",],}', 'UReflection'),
    ('slow', 'wonder', '```json\n{"thoughts":["생각"]}\n```', 'UWonder'),
    ('slow', 'importance', '{"score":5,"rationale":"이유",}', 'UImportance'),
])
async def test_each_loop_stage_checks_json_then_schema_and_logs_original(module, stage, raw, schema):
    from uxagent import schemas
    from uxagent.fast_loop import FastLoop
    from uxagent.slow_loop import _SlowModelIO
    from uxagent.llm import BudgetManager

    class Provider:
        async def complete(self, *args):
            return raw, {'provider': 'gpu', 'model': 'persona-qwen', 'input_tokens': 7, 'output_tokens': 3}

    records = []
    budget = BudgetManager(5, 10000)
    model = getattr(schemas, schema)
    if module == 'fast':
        loop = FastLoop(Provider(), budget, 'persona-qwen', 0, 512, records.append)
        parsed = await loop._generate(stage, 'Return JSON', {}, response_model=model)
    else:
        loop = _SlowModelIO()
        loop.provider, loop.budget, loop.model = Provider(), budget, 'persona-qwen'
        loop.temperature, loop.output_tokens, loop.call_log = 0, 512, records.append
        parsed = await loop._generate({'task_id': 'test-task'}, 'Return JSON', {}, stage, response_model=model)
    model.model_validate(parsed)
    assert len(records) == 1 and records[0]['response'] == raw
    assert records[0]['json_repairs']
    assert not records[0].get('error')
    assert budget.requests == 1 and budget.tokens == 10 and budget.reserved_tokens == 0


@pytest.mark.asyncio
async def test_invalid_api_envelope_never_triggers_model_json_repair():
    from uxagent.fast_loop import FastLoop
    from uxagent.llm import BudgetManager
    from uxagent.model_json import loads_transport_json, ProviderJSONError

    class Provider:
        attempts = 0

        async def complete(self, *args):
            self.attempts += 1
            return loads_transport_json('{"choices":invalid}')

    provider = Provider()
    loop = FastLoop(provider, BudgetManager(5, 10000), 'persona-qwen', 0, 512)
    with pytest.raises(ProviderJSONError):
        await loop._generate('plan', 'Return JSON', {})
    assert provider.attempts == 1


@pytest.mark.asyncio
async def test_setup_advice_uses_common_checker_before_its_schema():
    from uxagent.setup_guide import SetupGuide

    class Provider:
        async def complete(self, *args, **kwargs):
            return '{answer:"설정 안내",personas:[],task_suggestion:None,}', {'input_tokens': 1, 'output_tokens': 1}

    result = await SetupGuide(provider_factory=lambda _: Provider()).recommend('live', None, '안내', {}, [])
    assert result['answer'] == '설정 안내' and result['source'] == 'ai'


def test_persona_model_json_is_checked_before_persona_validation(tmp_path, monkeypatch):
    from pathlib import Path
    from uxagent.personas import generate_personas

    example = Path(__file__).resolve().parents[1] / 'configs/persona.json'
    persona = json.loads(example.read_text())

    class Provider:
        async def complete(self, *args, **kwargs):
            return json.dumps(persona)[:-1] + ',}', {'input_tokens': 1, 'output_tokens': 1}

    monkeypatch.setattr('uxagent.llm.OpenAIProvider', Provider)
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'count': 1, 'example_persona_file': str(example)}))
    out, count, total = generate_personas(config, tmp_path / 'output', 'live')
    assert count == total == 1
    assert json.loads(out.read_text())['persona_id'] == 'p001'


@pytest.mark.asyncio
async def test_summary_json_is_checked_and_repair_logged_without_extra_model_request():
    from uxagent.llm import LocalQwenProvider, BudgetManager

    provider = LocalQwenProvider()
    calls = []

    async def send(*args):
        return '{"summary":"관찰 핵심",}', {'input_tokens': 1, 'output_tokens': 1}

    provider._enqueue = send
    messages = [{'role': 'user', 'content': json.dumps({'memories': ['가' * 500] * 50})}]
    budget = BudgetManager(None, None)
    prepared = await provider.prepare_messages(messages, 'persona-qwen', 512,
        budget=budget, call_log=calls.append)
    assert provider.prompt_guard.fits(prepared, 512)
    assert all(call['repair_attempt'] == 0 and 'trailing_comma' in call['json_repairs'] for call in calls)
    assert budget.requests == len(calls) > 0
