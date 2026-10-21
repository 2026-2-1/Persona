"""Local SSH-tunnel client for the matching remote chat tokenizer."""
from __future__ import annotations

import hashlib
import json
import threading
import urllib.request
from collections import OrderedDict
from urllib.parse import urlsplit


class QwenTokenCounter:
    def __init__(self, url):
        parsed = urlsplit(url)
        if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or not parsed.port or parsed.path != '/tokenize' or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('Qwen tokenizer URL must be a local SSH /tokenize endpoint')
        self.url, self.cache, self.lock = url, OrderedDict(), threading.Lock()

    def count(self, messages):
        body = json.dumps({'model': 'persona-qwen', 'messages': messages}, ensure_ascii=False).encode()
        key = hashlib.sha256(body).hexdigest()
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return dict(self.cache[key])
        request = urllib.request.Request(self.url, data=body, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.loads(response.read())
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
