import json
import io
import urllib.error

import pytest

from uxagent.tokenizer_server import TokenizerEngine, read_chat_settings
from uxagent.token_counter import QwenTokenCounter


def test_tokenizer_reuses_server_model_and_identical_chat_template_options(tmp_path):
    script = tmp_path / 'server.py'
    script.write_text('MODEL_PATH="/models/qwen"\nMODEL_NAME="persona-qwen"\n')
    settings = read_chat_settings(script)
    assert settings == ('/models/qwen', 'persona-qwen')
    seen = {}
    class Tokens:
        shape = (1, 17)
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            seen.update(kwargs)
            return {'input_ids': Tokens()}
    engine = TokenizerEngine('/models/qwen', 'persona-qwen', tokenizer=Tokenizer())
    result = engine.count([{'role': 'user', 'content': '러닝화'}])
    assert result['prompt_tokens'] == 17
    assert seen == {'tokenize': True, 'add_generation_prompt': True,
                    'enable_thinking': False, 'return_dict': True, 'return_tensors': 'pt'}


def test_tokenizer_settings_are_read_without_executing_remote_script(tmp_path):
    script = tmp_path / 'server.py'
    script.write_text('raise RuntimeError("must not execute")\nMODEL_PATH="/model"\nMODEL_NAME="persona-qwen"\n')
    assert read_chat_settings(script) == ('/model', 'persona-qwen')
    script.write_text('MODEL_PATH=get_secret()\nMODEL_NAME="persona-qwen"\n')
    with pytest.raises(ValueError):
        read_chat_settings(script)


def test_counter_validates_model_and_uses_bounded_cache(monkeypatch):
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'model': 'persona-qwen', 'prompt_tokens': 33,
                'input_token_limit': 8192, 'max_output_tokens': 512,
                'tokenizer_fingerprint': 'test-fingerprint'}).encode()
    def request(req, timeout):
        calls.append(json.loads(req.data));return Response()
    monkeypatch.setattr('uxagent.token_counter.urllib.request.urlopen', request)
    counter = QwenTokenCounter('http://127.0.0.1:8003/tokenize')
    messages = [{'role': 'user', 'content': '검색'}]
    assert counter.count(messages)['prompt_tokens'] == 33
    assert counter.count(messages)['prompt_tokens'] == 33
    assert len(calls) == 1 and calls[0]['messages'] == messages
    with pytest.raises(ValueError):
        QwenTokenCounter('https://external.test/tokenize')


@pytest.mark.parametrize('body,expected', [
    (b'{"error":"tokenization_failed"}', 'tokenization_failed'),
    (b'{"error":"invalid_body_size"}', 'invalid_body_size'),
    (b'{"error":"PRIVATE_REQUEST_CONTENT"}', 'unknown'),
    (b'PRIVATE_REQUEST_CONTENT', 'unknown'),
    (b'["PRIVATE_REQUEST_CONTENT"]', 'unknown'),
    (b'{"error":{"secret":"PRIVATE_REQUEST_CONTENT"}}', 'unknown'),
])
def test_counter_http_error_retains_status_and_only_known_safe_code(monkeypatch, body, expected):
    calls = []

    def request(req, timeout):
        calls.append(req)
        raise urllib.error.HTTPError(req.full_url, 500, 'PRIVATE_REASON', {}, io.BytesIO(body))

    monkeypatch.setattr('uxagent.token_counter.urllib.request.urlopen', request)
    counter = QwenTokenCounter('http://127.0.0.1:8003/tokenize')
    for _ in range(2):
        with pytest.raises(RuntimeError) as error:
            counter.count([{'role': 'user', 'content': 'PRIVATE_REQUEST_CONTENT'}])
        assert str(error.value) == f'prompt_tokenizer_unavailable: HTTP 500 {expected}'
        assert 'PRIVATE' not in str(error.value)
    assert len(calls) == 2 and not counter.cache
