"""Embedding transport separate from the Qwen chat provider."""
from __future__ import annotations

import asyncio
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .model_json import loads_json, dumps_json


class LocalEmbeddingProvider:
    provider_name = 'local_embedding'

    def __init__(self):
        self.url = os.environ.get('PERSONA_EMBEDDING_API_URL', '')
        parsed = urlsplit(self.url)
        if (parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}
                or parsed.username or parsed.password or parsed.path != '/v1/embeddings'
                or parsed.query or parsed.fragment or not parsed.port):
            raise ValueError('임베딩 주소는 로컬 SSH 터널의 /v1/embeddings여야 합니다')

    async def embed(self, texts, model):
        return await asyncio.to_thread(self._embed, texts, model)

    def _embed(self, texts, model):
        request = urllib.request.Request(self.url,
            data=dumps_json({'model': model, 'input': texts}, ensure_ascii=False).encode(),
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = loads_json(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'embedding_http_{exc.code}') from None
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            raise RuntimeError('embedding_transport_error') from None
        usage = {
            'provider': 'local_embedding', 'model': data.get('model'),
            'input_tokens': data.get('usage', {}).get('prompt_tokens'), 'output_tokens': 0}
        try:
            rows = sorted(data['data'], key=lambda row: row['index'])
            if (any(type(row['index']) is not int for row in rows)
                    or [row['index'] for row in rows] != list(range(len(texts)))):
                raise ValueError('embedding response indices mismatch')
            vectors = [row['embedding'] for row in rows]
        except (KeyError, TypeError, ValueError):
            # Let the caller reject the payload after recording known usage.
            vectors = []
            usage['response_error'] = 'invalid_embedding_payload'
        return vectors, usage
