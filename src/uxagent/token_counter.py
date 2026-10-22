"""Local SSH-tunnel client for the matching remote chat tokenizer."""
from __future__ import annotations

import hashlib
import threading
import urllib.error
import urllib.request
from collections import OrderedDict
from urllib.parse import urlsplit

from .model_json import loads_json, dumps_json


class QwenTokenCounter:
    def __init__(self, url):
        parsed = urlsplit(url)
        if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or not parsed.port or parsed.path != '/tokenize' or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('Qwen tokenizer URL must be a local SSH /tokenize endpoint')
        self.url, self.cache, self.lock = url, OrderedDict(), threading.Lock()

    def count(self, messages):
        body = dumps_json({'model': 'persona-qwen', 'messages': messages}, ensure_ascii=False).encode()
        key = hashlib.sha256(body).hexdigest()
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return dict(self.cache[key])
        request = urllib.request.Request(self.url, data=body, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = loads_json(response.read())
        except urllib.error.HTTPError as exc:
            code = 'unknown'
            try:
                payload = loads_json(exc.read(4096))
                candidate = payload.get('error') if isinstance(payload, dict) else None
                if isinstance(candidate, str) and candidate in {
                        'not_found', 'invalid_body_size', 'invalid_model_or_messages',
                        'invalid_json', 'tokenization_failed'}:
                    code = candidate
            except Exception:
                pass  # Never expose an arbitrary response body, URL or reason.
            finally:
                exc.close()
            raise RuntimeError(f'prompt_tokenizer_unavailable: HTTP {exc.code} {code}') from None
        except Exception as exc:
            raise RuntimeError('prompt_tokenizer_unavailable: ' + type(exc).__name__) from None
        if (result.get('model') != 'persona-qwen' or type(result.get('prompt_tokens')) is not int
                or result['prompt_tokens'] < 0 or result.get('input_token_limit') != 8192
                or result.get('max_output_tokens') != 512
                or not isinstance(result.get('tokenizer_fingerprint'), str)
                or not result['tokenizer_fingerprint']):
            raise ValueError('Invalid Qwen tokenizer response')
        with self.lock:
            self.cache[key] = result
            while len(self.cache) > 256:
                self.cache.popitem(last=False)
        return dict(result)
