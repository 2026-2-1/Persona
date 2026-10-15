from __future__ import annotations

import math, time, uuid
from datetime import datetime, timezone
from .schemas import MemoryChangeEvent, MemoryEntry

FIXED_IMPORTANCE = 5


class MemoryStore:
    def __init__(self, run_id, writer=None, clock=time.monotonic, *, max_active_memories=64, change_writer=None):
        if not 10 <= max_active_memories <= 64:
            raise ValueError("max_active_memories must be between 10 and 64")
        self.run_id, self.writer, self.clock = run_id, writer, clock
        self.max_active_memories, self.change_writer = max_active_memories, change_writer
        self.entries: list[MemoryEntry] = []
        self.known_memory_ids: set[str] = set()
        self.started = clock()
        self._next_seq = 1
        self.embedding_cache: dict[str, list[float]] = {}

    def append(self, kind, text, source_step_ids=None, source_observation_ids=None,
               content_status="observed", based_on_seq=0, importance=FIXED_IMPORTANCE, *,
               source_memory_ids=None, source_stage_record_id=None):
        if importance is None:
            importance = FIXED_IMPORTANCE
        if importance != FIXED_IMPORTANCE:
            raise ValueError(f"new memory importance is fixed at {FIXED_IMPORTANCE}")
        seq=self._next_seq
        entry=MemoryEntry(schema_version="2.0",memory_id=f"m-{seq}-{uuid.uuid4().hex[:10]}",seq=seq,run_id=self.run_id,
            kind=kind,text=text,source_step_ids=source_step_ids or [],source_observation_ids=source_observation_ids or [],
            source_memory_ids=source_memory_ids or [],source_stage_record_id=source_stage_record_id,
            created_at=datetime.now(timezone.utc).isoformat(),created_monotonic_ms=int((self.clock()-self.started)*1000),
            based_on_seq=based_on_seq,importance=importance,content_status=content_status)
        self._next_seq += 1
        self.entries.append(entry)
        self.known_memory_ids.add(entry.memory_id)
        if self.writer: self.writer.write(entry.model_dump())
        self._enforce_active_limit()
        return entry

    def _enforce_active_limit(self):
        while len(self.entries) > self.max_active_memories:
            protected_ids = {entry.memory_id for entry in self.entries[-10:]}
            eligible = [entry for entry in self.entries if entry.memory_id not in protected_ids]

            def retention_key(entry):
                if entry.importance is None:
                    return (False, 0.0, entry.seq)
                maximum = 5 if entry.schema_version == "1.0" else 10
                return (True, entry.importance / maximum, entry.seq)

            ranked = sorted(eligible, key=retention_key)
            victim = ranked[0]
            # Keep the recorded score consistent with importance-first ordering.
            oldest_seq, newest_seq = eligible[0].seq, eligible[-1].seq
            recency = (victim.seq - oldest_seq) / max(1, newest_seq - oldest_seq)
            if victim.importance is None:
                retention_score = (0.05 * recency) / 2.05
            else:
                maximum = 5 if victim.schema_version == "1.0" else 10
                retention_score = (1 + victim.importance / maximum + 0.05 * recency) / 2.05
            event = MemoryChangeEvent(
                event_id=f"memory-change-{uuid.uuid4().hex}", run_id=self.run_id,
                memory_id=victim.memory_id, memory_seq=victim.seq, change="evicted",
                importance_before=victim.importance if victim.schema_version == "2.0" else None,
                retention_score=retention_score,
                reason_code="active_capacity_importance_then_recency",
                recorded_at=datetime.now(timezone.utc),
            )
            if self.change_writer: self.change_writer.write(event.model_dump())
            self.entries.remove(victim)
            self.embedding_cache.pop(victim.memory_id, None)

    def update_importance(self, memory_id: str, importance: int, source_stage_record_id: str):
        raise RuntimeError(f"importance scores are fixed at {FIXED_IMPORTANCE}; score updates are disabled")

    def retrieve(self, query: str, limit=8, now_ms=None, embeddings: dict[str,list[float]]|None=None, mode="fast"):
        now_ms = int((self.clock()-self.started)*1000) if now_ms is None else now_ms
        # Equal I/Q/R weights are the temporary #40 baseline; module tuning is #54.
        weights=(1/3,1/3,1/3)
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
            importance_max=5 if e.schema_version=="1.0" else 10
            components=[(weights[0],e.importance/importance_max if e.importance is not None else None),
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
                active_ids={entry.memory_id for entry in self.entries}
                for entry,vector in zip(missing,vectors[offset:]):
                    if entry.memory_id in active_ids:self.embedding_cache[entry.memory_id]=vector
                if call_log:call_log({"module":"embedding","model":usage.get("model",model),"elapsed_ms":int((time.monotonic()-started)*1000),"input_tokens":actual,"estimated":actual is None,"cached_embeddings":len(missing)})
            except BaseException as exc:
                if not settled:budget.settle(reservation,None)
                if call_log:call_log({"module":"embedding","model":model,"elapsed_ms":int((time.monotonic()-started)*1000),"error":str(exc)[:300]})
                raise
        return self.retrieve(query,limit,embeddings=self.embedding_cache)
