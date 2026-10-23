"""CPU token counting beside the existing Qwen server, in its Python venv."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def read_chat_settings(path):
    values = {}
    for node in ast.parse(Path(path).read_text()).body:
        if isinstance(node, ast.Assign):
            for name in node.targets:
                if isinstance(name, ast.Name) and name.id in {'MODEL_PATH', 'MODEL_NAME'}:
                    if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
                        raise ValueError('Chat model settings must be literal strings')
                    values[name.id] = node.value.value
    if set(values) != {'MODEL_PATH', 'MODEL_NAME'} or values['MODEL_NAME'] != 'persona-qwen':
        raise ValueError('Cannot verify the chat server model/tokenizer settings')
    return values['MODEL_PATH'], values['MODEL_NAME']


class TokenizerEngine:
    def __init__(self, model_path, model_name, *, tokenizer=None):
        if tokenizer is None:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.tokenizer, self.model_name = tokenizer, model_name
        self.lock = threading.Lock()
        digest = hashlib.sha256()
        for name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja'):
            path = Path(model_path) / name
            if path.exists():
                digest.update(name.encode());digest.update(path.read_bytes())
        self.fingerprint = digest.hexdigest()

    def health(self):
        return {'status': 'ok', 'model': self.model_name, 'input_token_limit': 8192,
                'max_output_tokens': 512, 'tokenizer_fingerprint': self.fingerprint}

    def count(self, messages):
        # Deliberately identical to api_server.py. Only .to(cuda) and generation
        # are omitted; the prompt's token IDs are produced by the same template.
        with self.lock:
            inputs = self.tokenizer.apply_chat_template(messages, tokenize=True,
                add_generation_prompt=True, enable_thinking=False,
                return_dict=True, return_tensors='pt')
        return {**self.health(), 'prompt_tokens': inputs['input_ids'].shape[1]}


def make_tokenizer_handler(engine):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def reply(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers();self.wfile.write(body)

        def do_GET(self):
            self.reply(200, engine.health()) if self.path == '/health' else self.reply(404, {'error': 'not_found'})

        def do_POST(self):
            if self.path != '/tokenize':
                return self.reply(404, {'error': 'not_found'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1024 * 1024:
                    return self.reply(413, {'error': 'invalid_body_size'})
                data = json.loads(self.rfile.read(length))
                messages = data.get('messages')
                if (data.get('model') != engine.model_name or not isinstance(messages, list)
                        or not messages or any(not isinstance(m, dict) or
                        m.get('role') not in {'system', 'user', 'assistant'} or
                        not isinstance(m.get('content'), str) for m in messages)):
                    return self.reply(400, {'error': 'invalid_model_or_messages'})
            except (ValueError, AttributeError):
                return self.reply(400, {'error': 'invalid_json'})
            try:
                result = engine.count(messages)
            except Exception:
                return self.reply(500, {'error': 'tokenization_failed'})
            self.reply(200, result)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server-script', required=True)
    parser.add_argument('--port', type=int, default=8003)
    args = parser.parse_args()
    model_path, model_name = read_chat_settings(args.server_script)
    engine = TokenizerEngine(model_path, model_name)
    with ThreadingHTTPServer(('127.0.0.1', args.port), make_tokenizer_handler(engine)) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
