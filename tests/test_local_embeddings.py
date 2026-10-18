import asyncio
import json

import pytest

from uxagent.embeddings import LocalEmbeddingProvider


def test_local_embedding_has_separate_endpoint_model_and_no_ssh_credentials(monkeypatch):
    monkeypatch.setenv('PERSONA_EMBEDDING_API_URL', 'http://127.0.0.1:8002/v1/embeddings')
    seen={}
    class Response:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def read(self): return json.dumps({'model':'embed-model','data':[{'index':1,'embedding':[0.,1.]},{'index':0,'embedding':[1.,0.]}],'usage':{'prompt_tokens':7}}).encode()
    def request(req, timeout):
        seen.update(url=req.full_url,body=json.loads(req.data),headers=dict(req.header_items()),timeout=timeout)
        return Response()
    monkeypatch.setattr('uxagent.embeddings.urllib.request.urlopen',request)
    vectors,usage=asyncio.run(LocalEmbeddingProvider().embed(['first','second'],'embed-model'))
    assert vectors==[[1.,0.],[0.,1.]] and usage['input_tokens']==7
    assert usage['provider']=='local_embedding'
    assert seen['url'].endswith(':8002/v1/embeddings') and seen['timeout']==120
    assert seen['body']=={'model':'embed-model','input':['first','second']}
    assert 'Authorization' not in seen['headers']


@pytest.mark.parametrize('url',['http://example.com:8002/v1/embeddings','http://user:pass@localhost:8002/v1/embeddings','http://localhost:8002/v1/chat/completions'])
def test_embedding_endpoint_requires_local_tunnel(monkeypatch,url):
    monkeypatch.setenv('PERSONA_EMBEDDING_API_URL',url)
    with pytest.raises(ValueError,match='임베딩'): LocalEmbeddingProvider()


def test_gpu_configuration_can_choose_separate_local_embedding(monkeypatch):
    from uxagent.runner import validate_provider_configuration
    from uxagent.schemas import StudyConfig
    from pathlib import Path
    raw=json.loads(Path('configs/study.json').read_text()); raw.update(embedding_provider='local',embedding_model='embed-model')
    monkeypatch.setenv('PERSONA_EMBEDDING_API_URL','http://127.0.0.1:8002/v1/embeddings')
    validate_provider_configuration('gpu',StudyConfig.model_validate(raw))


def test_standalone_embedding_api_uses_real_http_without_chat_provider():
    import threading
    import urllib.request
    from http.server import HTTPServer
    from uxagent.embedding_server import make_embedding_handler, EmbeddingEngine
    class Array:
        def tolist(self): return [[2.,3.],[4.,5.]]
    class Count:
        def sum(self): return self
        def item(self): return 7
    class Encoder:
        device='cuda:0'; max_seq_length=128
        def get_sentence_embedding_dimension(self): return 2
        def encode(self,texts,**kwargs):
            assert texts==['first','second'] and kwargs['normalize_embeddings'] is False
            return Array()
        def tokenize(self,texts): return {'attention_mask':Count()}
    engine=EmbeddingEngine('embed-model',encoder=Encoder())
    server=HTTPServer(('127.0.0.1',0),make_embedding_handler(engine))
    worker=threading.Thread(target=server.serve_forever);worker.start()
    try:
        url='http://127.0.0.1:'+str(server.server_port)
        with urllib.request.urlopen(url+'/health') as response: health=json.loads(response.read())
        assert health['dimension']==2 and health['device']=='cuda:0'
        request=urllib.request.Request(url+'/v1/embeddings',data=json.dumps({'model':'embed-model','input':['first','second']}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response: result=json.loads(response.read())
        assert result['data'][1]['embedding']==[4.,5.] and result['usage']['prompt_tokens']==7
    finally:
        server.shutdown();worker.join();server.server_close()


@pytest.mark.asyncio
async def test_slow_update_uses_separate_embedding_transport_and_shared_budget():
    from uxagent.llm import MockProvider, BudgetManager
    from uxagent.memory import MemoryStore
    from uxagent.slow_loop import ContinuousSlowLoop
    class Chat(MockProvider):
        async def embed(self,*args): raise AssertionError('chat must not embed')
    class Embed:
        provider_name='local_embedding'
        def __init__(self): self.inputs=[]
        async def embed(self,texts,model):
            self.inputs.append((texts,model))
            return [[1.,0.] for _ in texts],{'provider':'local_embedding','model':model,'input_tokens':8}
    store=MemoryStore('separate');entry=store.append('observation','page')
    embedding=Embed();budget=BudgetManager(None,None);logs=[]
    slow=ContinuousSlowLoop(Chat(),budget,'mock-v1',.2,100,store,call_log=logs.append,
        embedding_model='embed-model',embedding_provider=embedding)
    slow.persona={};slow.intent='task';slow.plan_getter=lambda:None;slow.observation_id=None
    await slow.update_memory()
    assert embedding.inputs==[(['page'],'embed-model')]
    assert store.embedding_cache[entry.memory_id]==[1.,0.] and entry.importance==5
    assert budget.requests==2 and budget.tokens==8 and budget.reserved_tokens==0
    assert {row['provider'] for row in logs}=={'mock','local_embedding'}
