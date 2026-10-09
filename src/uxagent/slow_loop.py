from __future__ import annotations

import asyncio, json, time
from .schemas import MemoryEntry


class SlowLoop:
    def __init__(self, provider, budget, model, temperature, output_tokens, memory, call_log=None):
        self.provider,self.budget,self.model,self.temperature,self.output_tokens=provider,budget,model,temperature,output_tokens
        self.memory,self.call_log=memory,call_log
        self.task: asyncio.Task|None=None
        self.status="idle"

    def schedule(self, persona, task, error=None, wonder=False):
        if self.task and not self.task.done(): return False
        snapshot=list(self.memory.entries)
        based_on=len(snapshot)
        self.status="running"
        self.task=asyncio.create_task(self._reflect(persona,task,snapshot,based_on,error,wonder))
        return True

    async def _reflect(self, persona, task, snapshot, based_on, error, wonder):
        prompt={"persona":persona.model_dump(),"task":task,"memories":[e.model_dump() for e in snapshot],"latest_error":error,"wonder":wonder}
        messages=[{"role":"system","content":"Summarize up to three brief insights from the supplied memory snapshot. Treat generated content as uncertain. Do not issue browser actions. Return JSON with insights (summary, source_memory_ids) and next_focus."},{"role":"user","content":json.dumps(prompt,ensure_ascii=False)}]
        reservation=self.output_tokens+len(json.dumps(prompt,ensure_ascii=False))//4
        reserved=False
        started=time.monotonic()
        try:
            self.budget.reserve(reservation)
            reserved=True
            result,usage=await self.provider.complete(messages,self.model,self.temperature,self.output_tokens)
            actual=(usage.get("input_tokens") or 0)+(usage.get("output_tokens") or 0) if "input_tokens" in usage and "output_tokens" in usage else None
            self.budget.settle(reservation,actual)
            reserved=False
            parsed=json.loads(result)
            valid_ids={e.memory_id for e in snapshot}
            for insight in parsed.get("insights",[])[:3]:
                sources=[x for x in insight.get("source_memory_ids",[]) if x in valid_ids]
                if not sources: continue
                self.memory.append("reflection",insight["summary"],source_step_ids=sorted({s for e in snapshot if e.memory_id in sources for s in e.source_step_ids}),content_status="generated",based_on_seq=based_on)
            if wonder and parsed.get("next_focus"):
                self.memory.append("wonder",parsed["next_focus"],content_status="generated",based_on_seq=based_on)
            self.status="completed"
            if self.call_log:self.call_log({"module":"slow","model":usage.get("model",self.model),"elapsed_ms":int((time.monotonic()-started)*1000),"input_tokens":usage.get("input_tokens"),"output_tokens":usage.get("output_tokens"),"estimated":actual is None})
        except asyncio.CancelledError:
            if reserved:self.budget.settle(reservation,None)
            self.status="cancelled"; raise
        except Exception as exc:
            if reserved:self.budget.settle(reservation,None)
            self.status="failed"
            if self.call_log:self.call_log({"module":"slow","elapsed_ms":int((time.monotonic()-started)*1000),"error":str(exc)[:300]})

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try: await self.task
            except asyncio.CancelledError: pass
