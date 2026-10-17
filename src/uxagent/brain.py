from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from .fast_loop import FastLoop
from .llm import BudgetExceeded
from .schemas import BrainTaskEvent, BrainStageRecord, AgentDecision


class Brain:
    """Run-scoped coordinator for staged Fast decisions and asynchronous Slow work."""

    STAGES = {"perception", "feedback", "plan", "decision"}

    def __init__(self, fast_loop: FastLoop, slow_loop, memory, persona, persona_mode="persona",
                 task_writer=None, *, stage_writer=None):
        if persona_mode not in {"general", "persona"}:
            raise ValueError("persona_mode must be general or persona")
        self.fast = fast_loop
        self.slow = slow_loop
        self.memory = memory
        self.persona = persona
        self.persona_mode = persona_mode
        self.task_writer = task_writer
        self.stage_writer = stage_writer
        self.current_plan = None
        self.last_action = None
        self.slow_started = False
        self.current_observation_id = None
        self.current_plan_id = None
        self.current_plan_version = None
        self.fast_inflight = {}
        self.fast_counts = {stage: {key: 0 for key in
                           ("scheduled", "started", "completed", "failed", "skipped", "cancelled")}
                           for stage in self.STAGES}
        self.adoption_counts = {"reflection": 0, "plan_review": 0, "wonder": 0, "discarded": 0}

    async def forward(self, intent, observation, step_id, retrieve):
        """U Fast flow. Record IDs describe results; they do not authorize generation."""
        self.current_observation_id = observation.observation_id
        self.current_plan_id = self.current_plan_version = None

        async def perceive():
            result = await self._u_call("perception", observation, [],
                                        lambda: self.fast.perceive_page(observation))
            if not result.observations or not result.observations[0].strip():
                self._fail_fast("perception", self.fast_task_id("perception"),
                                ValueError("empty_observations"))
                raise ValueError("observations must contain a nonempty first observation")
            record = self._u_record("perception", observation, result.observations[0], [], result)
            self._u_memory("observation", result.observations[0], step_id, observation, record)
            return result.observations[0]

        async def feedback():
            result = await self._u_call("feedback", observation, [], lambda: self.fast.feedback(
                self.persona, json.dumps(self.last_action, ensure_ascii=False), self.current_plan.plan,
                observation, self.persona_mode))
            record = self._u_record("feedback", observation, "\n".join(result.thoughts) or "[]", [], result)
            for thought in result.thoughts:
                self._u_memory("thought", thought, step_id, observation, record)

        if self.memory.timestamp:
            # Join both tasks before proceeding and clean up the sibling on error/cancel.
            tasks = [asyncio.create_task(feedback()), asyncio.create_task(perceive())]
            try:
                _, perception = await asyncio.gather(*tasks)
            except BaseException:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
        else:
            perception = await perceive()
        if not self.slow_started:
            self.schedule_reflection(intent, observation.observation_id)
            self.slow_started = True

        self._consume_u_completed()
        plan_memories = await retrieve(intent, "fast_plan")
        plan = await self._u_call("plan", observation, plan_memories, lambda: self.fast.make_plan(
            self.persona, intent, plan_memories, self.memory.timestamp, self.current_plan, self.persona_mode))
        self.current_plan_id, self.current_plan_version = f"plan-{uuid.uuid4().hex}", 1
        plan_record = self._u_record("plan", observation, plan.plan, plan_memories, plan)
        self.current_plan = plan
        self._u_memory("thought", plan.rationale, step_id, observation, plan_record)
        self._u_memory("plan", plan.plan, step_id, observation, plan_record)

        self._consume_u_completed()
        action_memories = await retrieve(plan.next_step, "fast_decision")
        proposed = await self._u_call("decision", observation, action_memories, lambda: self.fast.act(
            self.persona, intent, observation, action_memories, plan, self.persona_mode))
        action_record = self._u_record("decision", observation,
            "\n".join(action.description for action in proposed.actions), action_memories, proposed)
        for action in proposed.actions:
            self._u_memory("action", action.description, step_id, observation, action_record,
                           raw_action=action.model_dump(exclude_none=True))
        # U records all proposals and executes only the first one.
        self.last_action = proposed.actions[-1].model_dump(exclude_none=True)
        action, finish = self.fast.adapt_action(proposed.actions[0], observation)
        self.memory.timestamp += 1
        return AgentDecision(decision_id=f"d-{uuid.uuid4().hex[:10]}", perception=perception,
            plan=plan.plan, rationale_summary=proposed.actions[0].description, action=action,
            finish=finish, proposed_actions=proposed.actions, next_step=plan.next_step), action_record.source_memory_ids

    async def _u_call(self, stage, observation, memories, call):
        task_id = self._start_fast(stage, observation.observation_id, memories)
        try:
            return await call()
        except BaseException as exc:
            self._fail_fast(stage, task_id, exc)
            raise

    def _u_record(self, stage, observation, text, memories, response):
        record = BrainStageRecord(record_id=f"stage-{stage}-{uuid.uuid4().hex}",
            task_id=self.fast_task_id(stage), run_id=self.memory.run_id, stage=stage,
            observation_id=observation.observation_id,
            plan_id=self.current_plan_id if stage in {"plan", "decision"} else None,
            plan_version=self.current_plan_version if stage in {"plan", "decision"} else None,
            source_memory_ids=[m["memory_id"] for m in memories], text=text,
            model_response=response.model_dump(exclude_none=True), recorded_at=datetime.now(timezone.utc))
        if self.stage_writer:
            self.stage_writer.write(record.model_dump())
        self.complete_fast(stage, record)
        return record

    def _u_memory(self, kind, text, step_id, observation, record, *, raw_action=None):
        return self.memory.append(kind, text, [step_id], [observation.observation_id], "generated",
            source_memory_ids=record.source_memory_ids, source_stage_record_id=record.record_id,
            raw_action=raw_action)

    def _consume_u_completed(self):
        # Temporary bridge to #84's scheduler: publish completed outputs directly to
        # shared memory. No observation/plan-version gate or priority insertion.
        adopted_memories = []
        for result in self.slow.pop_completed():
            for output in result["outputs"]:
                adopted_memories.append(self._append_output(output, result["snapshot_seq"]).model_dump())
            adopted = bool(result["outputs"])
            self.slow.record_consumption(result, adopted=adopted,
                                         reason_code=None if adopted else "no_usable_output")
            key = result["kind"] if adopted else "discarded"
            self.adoption_counts[key] = self.adoption_counts.get(key, 0) + 1
        return adopted_memories

    def begin_stage(self, stage, observation_id, *, plan_id=None, plan_version=None):
        if stage not in self.STAGES:
            raise ValueError(f"unsupported Brain stage: {stage}")
        if stage == "perception":
            self.current_observation_id = observation_id
            self.current_plan_id = self.current_plan_version = None
        if stage == "decision":
            self.current_plan_id, self.current_plan_version = plan_id, plan_version
        return self._consume_u_completed()

    async def perceive(self, task, observation, memories):
        task_id = self._start_fast("perception", observation.observation_id, memories)
        try:
            return await self.fast.perceive(self.persona, task, observation, memories,
                                            self.persona_mode)
        except BaseException as exc:
            self._fail_fast("perception", task_id, exc)
            raise

    async def plan(self, task, observation, memories, perception, previous_error,
                   recent_actions, remaining_steps):
        task_id = self._start_fast("plan", observation.observation_id, memories)
        try:
            return await self.fast.plan(self.persona, task, observation, memories, perception,
                                        previous_error, self.persona_mode, recent_actions,
                                        remaining_steps)
        except BaseException as exc:
            self._fail_fast("plan", task_id, exc)
            raise

    async def decide_action(self, task, observation, memories, perception, plan,
                            previous_error, remaining_steps, recent_actions=None):
        task_id = self._start_fast("decision", observation.observation_id, memories)
        try:
            return await self.fast.decide_action(
                self.persona, task, observation, memories, perception, plan, previous_error,
                remaining_steps, self.persona_mode, recent_actions=recent_actions,
            )
        except BaseException as exc:
            self._fail_fast("decision", task_id, exc)
            raise

    def fast_task_id(self, stage):
        return self.fast_inflight.get(stage)

    def complete_fast(self, stage, record):
        task_id = self.fast_inflight.pop(stage, None)
        if not task_id:
            raise RuntimeError(f"no in-flight Fast task for {stage}")
        self._fast_event(stage, task_id, "completed", source_memory_ids=record.source_memory_ids,
                         output_record_ids=[record.record_id])

    def schedule_reflection(self, task, observation_id, *, error=None, wonder=False):
        return self.slow.schedule_reflection(self._slow_persona(), task, observation_id,
                                             error=error, wonder=wonder)

    def schedule_plan_review(self, task, plan, observation_id, plan_id, plan_version):
        return self.slow.schedule_plan_review(self._slow_persona(), task, plan, observation_id,
                                              plan_id, plan_version)

    async def close(self):
        self.memory.set_current_stage_memories([])
        await self.slow.close()
        for result in self.slow.pop_completed():
            self.slow.record_consumption(result, adopted=False,
                                         reason_code="run_finished_unconsumed")
        for stage, task_id in list(self.fast_inflight.items()):
            self.fast_inflight.pop(stage, None)
            self._fast_event(stage, task_id, "failed", reason_code="stage_record_missing")

    def summary(self):
        slow = self.slow.summary()
        events = slow["events"]
        finished = events["completed"] + events["failed"] + events["skipped"] + events["cancelled"]
        complete = events["scheduled"] > 0 and finished == events["scheduled"] and not any(
            events[key] for key in ("failed", "skipped", "cancelled"))
        fast_complete = all(
            counters["scheduled"] > 0
            and counters["completed"] == counters["scheduled"]
            and not counters["failed"] and not counters["skipped"] and not counters["cancelled"]
            for stage, counters in self.fast_counts.items()
            if stage != "feedback" or counters["scheduled"]
        )
        return {
            "status": "completed" if complete and fast_complete else "incomplete",
            "fast": {stage: dict(counts) for stage, counts in self.fast_counts.items()},
            "slow": slow,
            "adoption": dict(self.adoption_counts),
        }

    def _append_output(self, output, snapshot_seq):
        return self.memory.append(
            output["kind"], output["text"], output["source_step_ids"],
            output["source_observation_ids"], "generated", snapshot_seq,
            source_memory_ids=output["source_memory_ids"],
            source_stage_record_id=output["record"].record_id,
        )

    def _slow_persona(self):
        context = FastLoop._persona_context(self.persona, self.persona_mode)
        if self.persona_mode == "general" and set(context) != {"constraints", "intent"}:
            raise ValueError("general condition Slow context must contain only shared constraints and intent")
        return context

    def _start_fast(self, stage, observation_id, memories):
        task_id = f"fast-{stage}-{uuid.uuid4().hex}"
        self.fast_inflight[stage] = task_id
        self._fast_event(stage, task_id, "scheduled", observation_id=observation_id,
                         source_memory_ids=[m["memory_id"] for m in memories if m.get("memory_id")])
        self._fast_event(stage, task_id, "started", observation_id=observation_id,
                         source_memory_ids=[m["memory_id"] for m in memories if m.get("memory_id")])
        return task_id

    def _fail_fast(self, stage, task_id, exc):
        self.fast_inflight.pop(stage, None)
        if isinstance(exc, BudgetExceeded):
            status, reason = "skipped", "budget_exceeded"
        elif isinstance(exc, asyncio.CancelledError):
            status, reason = "cancelled", "stage_cancelled"
        else:
            status, reason = "failed", f"{stage}_call_failed"
        self._fast_event(stage, task_id, status, reason_code=reason)

    def _fast_event(self, stage, task_id, status, *, observation_id=None,
                    source_memory_ids=None, output_record_ids=None, reason_code=None):
        self.fast_counts[stage][status] += 1
        if self.task_writer is None:
            return
        plan_id = self.current_plan_id if stage == "decision" else None
        plan_version = self.current_plan_version if stage == "decision" else None
        event = BrainTaskEvent(
            event_id=f"event-{uuid.uuid4().hex}", task_id=task_id,
            run_id=self.memory.run_id, kind=stage, status=status,
            snapshot_seq=max((entry.seq for entry in self.memory.entries), default=0),
            observation_id=observation_id or self.current_observation_id,
            plan_id=plan_id, plan_version=plan_version,
            source_memory_ids=source_memory_ids or [], output_record_ids=output_record_ids or [],
            reason_code=reason_code, recorded_at=datetime.now(timezone.utc),
        )
        self.task_writer.write(event.model_dump())
