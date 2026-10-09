from __future__ import annotations

import math, time, uuid
from datetime import datetime, timezone
from .schemas import MemoryEntry


class MemoryStore:
    def __init__(self, run_id, writer=None, clock=time.monotonic):
        self.run_id, self.writer, self.clock = run_id, writer, clock
        self.entries: list[MemoryEntry] = []
        self.started = clock()
        self.embedding_cache: dict[str, list[float]] = {}

    def append(self, kind, text, source_step_ids=None, source_observation_ids=None,
               content_status="observed", based_on_seq=0, importance=None):
        entry=MemoryEntry(memory_id="m-"+uuid.uuid4().hex[:10],seq=len(self.entries)+1,run_id=self.run_id,
            kind=kind,text=text,source_step_ids=source_step_ids or [],source_observation_ids=source_observation_ids or [],
            created_at=datetime.now(timezone.utc).isoformat(),created_monotonic_ms=int((self.clock()-self.started)*1000),
            based_on_seq=based_on_seq,importance=importance,content_status=content_status)
        self.entries.append(entry)
        if self.writer: self.writer.write(entry.model_dump())
        return entry

    def retrieve(self, query: str, limit=8, now_ms=None, embeddings: dict[str,list[float]]|None=None, mode="fast"):
        now_ms = int((self.clock()-self.started)*1000) if now_ms is None else now_ms
        weights=(.2,.3,.5) if mode=="fast" else (.3,.5,.2)
        qtokens=set(query.lower().split())
        scored=[]
        for e in self.entries:
            age=max(0,now_ms-e.created_monotonic_ms)/1000
            recency=math.exp(-math.log(2)*age/60)
            overlap=len(qtokens & set(e.text.lower().split()))/max(1,len(qtokens))
            relevance=(overlap if qtokens else None)
            vector=(embeddings or self.embedding_cache).get(e.memory_id)
            query_vector=self.embedding_cache.get("query:"+query)
            if vector and query_vector:
                a=query_vector; denom=math.sqrt(sum(x*x for x in a)*sum(x*x for x in vector))
                relevance=(sum(x*y for x,y in zip(a,vector))/denom+1)/2 if denom else 0
            components=[(weights[0],e.importance/5 if e.importance is not None else None),
                        (weights[1],relevance),(weights[2],recency)]
            used=[(w,v) for w,v in components if v is not None]
            score=sum(w*v for w,v in used)/sum(w for w,_ in used) if used else recency
            scored.append((score,e))
        scored.sort(key=lambda x:(x[0],x[1].seq),reverse=True)
        chosen=[]; source_steps=set()
        for score,e in scored:
            if e.source_step_ids and all(s in source_steps for s in e.source_step_ids): continue
            chosen.append({**e.model_dump(),"retrieval_score":score})
            source_steps.update(e.source_step_ids)
            if len(chosen)>=limit: break
        return chosen

    async def retrieve_with_embeddings(self, query, limit, provider, budget, model, call_log=None):
        if not self.entries:return []
        query_key="query:"+query
        missing=[entry for entry in self.entries if entry.memory_id not in self.embedding_cache]
        texts=[]
        if query_key not in self.embedding_cache:texts.append(query)
        texts.extend(entry.text for entry in missing)
        if texts:
            reservation=max(1,sum(len(text) for text in texts)*2+128)
            budget.reserve(reservation)
            started=time.monotonic();settled=False
            try:
                vectors,usage=await provider.embed(texts,model)
                actual=usage.get("input_tokens") if "input_tokens" in usage else None
                budget.settle(reservation,actual);settled=True
                offset=0
                if query_key not in self.embedding_cache:
                    self.embedding_cache[query_key]=vectors[0];offset=1
                for entry,vector in zip(missing,vectors[offset:]):self.embedding_cache[entry.memory_id]=vector
                if call_log:call_log({"module":"embedding","model":usage.get("model",model),"elapsed_ms":int((time.monotonic()-started)*1000),"input_tokens":actual,"estimated":actual is None,"cached_embeddings":len(missing)})
            except BaseException as exc:
                if not settled:budget.settle(reservation,None)
                if call_log:call_log({"module":"embedding","model":model,"elapsed_ms":int((time.monotonic()-started)*1000),"error":str(exc)[:300]})
                raise
        return self.retrieve(query,limit,embeddings=self.embedding_cache)
