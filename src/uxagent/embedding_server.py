"""Standalone remote embedding API; run in its own GPU Python environment."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class EmbeddingEngine:
    def __init__(self, model_name, *, device='cuda', encoder=None):
        if encoder is None:
            from sentence_transformers import SentenceTransformer
            encoder = SentenceTransformer(model_name, device=device, local_files_only=True,
                                          trust_remote_code=False)
        self.encoder, self.model_name = encoder, model_name

    def health(self):
        return {'status':'ok', 'model':self.model_name,
                'dimension':self.encoder.get_sentence_embedding_dimension(),
                'max_seq_length':self.encoder.max_seq_length,
                'device':str(self.encoder.device)}

    def embed(self, texts):
        # No normalization or query prefixes: search consumes the returned dot product.
        vectors = self.encoder.encode(texts, batch_size=16, show_progress_bar=False,
                                      normalize_embeddings=False).tolist()
        token_count = int(self.encoder.tokenize(texts)['attention_mask'].sum().item())
        return {'model':self.model_name,
                'data':[{'index':i, 'embedding':vector} for i, vector in enumerate(vectors)],
                'usage':{'prompt_tokens':token_count, 'total_tokens':token_count}}


def make_embedding_handler(engine):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, payload):
            body=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            self.reply(200,engine.health()) if self.path=='/health' else self.reply(404,{'error':'not_found'})

        def do_POST(self):
            if self.path!='/v1/embeddings':
                return self.reply(404,{'error':'not_found'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16*1024*1024:
                    return self.reply(413,{'error':'invalid_body_size'})
                payload=json.loads(self.rfile.read(length))
                texts=payload.get('input')
                if (payload.get('model')!=engine.model_name or not isinstance(texts,list)
                        or not 1<=len(texts)<=64 or any(not isinstance(text,str) for text in texts)):
                    return self.reply(400,{'error':'invalid_model_or_input'})
            except (ValueError, AttributeError):
                return self.reply(400,{'error':'invalid_json'})
            try:
                result=engine.embed(texts)
            except Exception:
                return self.reply(500,{'error':'embedding_failed'})
            return self.reply(200,result)
    return Handler


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',required=True)
    parser.add_argument('--port',type=int,default=8002)
    parser.add_argument('--device',default='cuda',choices=['cuda','cpu'])
    args=parser.parse_args()
    engine=EmbeddingEngine(args.model,device=args.device)
    # Bind only on the compute node's loopback; SSH forwards the port.
    with HTTPServer(('127.0.0.1',args.port),make_embedding_handler(engine)) as server:
        server.serve_forever()


if __name__=='__main__':
    main()
