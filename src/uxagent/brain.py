from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from .fast_loop import FastLoop
from .llm import BudgetExceeded
from .schemas import BrainTaskEvent


class Brain:
    """Run-scoped coordinator for staged Fast decisions and asynchronous Slow work."""

    STAGES = {"perception", "plan", "decision"}

    def __init__(self, fast_loop: FastLoop, slow_loop, memory, persona, persona_mode="persona",
                 task_writer=None):
        if persona_mode not in {"general", "persona"}:
            raise ValueError("persona_mode must be general or persona")
        self.fast = fast_loop
        self.slow = slow_loop
        self.memory = memory
        self.persona = persona
        self.persona_mode = persona_mode
        self.task_writer = task_writer
        self.current_observation_id = None
        self.current_plan_id = None
        self.current_plan_version = None
        self.fast_inflight = {}
        self.fast_counts = {stage: {key: 0 for key in
                           ("scheduled", "started", "completed", "failed", "skipped", "cancelled")}
                           for stage in self.STAGES}
        self.adoption_counts = {"reflection": 0, "plan_review": 0, "discarded": 0}

    def begin_stage(self, stage, observation_id, *, plan_id=None, plan_version=None):
        if stage not in self.STAGES:
            raise ValueError(f"unsupported Brain stage: {stage}")
        if stage == "perception":
            self.current_observation_id = observation_id
            self.current_plan_id = self.current_plan_version = None
        elif observation_id != self.current_observation_id:
            raise ValueError("Fast stages must use the current observation")
        if stage == "decision":
            if not plan_id or not plan_version:
                raise ValueError("decision stage requires a current plan ID and version")
            self.current_plan_id, self.current_plan_version = plan_id, plan_version
        return self._consume_completed(stage, observation_id, plan_id, plan_version)

    async def perceive(self, task, observation, memories):
        self._require_observation(observation.observation_id, "perception")
        task_id = self._start_fast("perception", observation.observation_id, memories)
        try:
            return await self.fast.perceive(self.persona, task, observation, memories,
                                            self.persona_mode)
        except BaseException as exc:
            self._fail_fast("perception", task_id, exc)
            raise

    async def plan(self, task, observation, memories, perception, previous_error,
                   recent_actions, remaining_steps):
        self._require_observation(observation.observation_id, "plan")
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
        self._require_observation(observation.observation_id, "decision")
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
            for counters in self.fast_counts.values()
        )
        return {
            "status": "completed" if complete and fast_complete else "incomplete",
            "fast": {stage: dict(counts) for stage, counts in self.fast_counts.items()},
            "slow": slow,
            "adoption": dict(self.adoption_counts),
        }

    def _consume_completed(self, stage, observation_id, plan_id, plan_version):
        adopted_memories = []
        for result in self.slow.pop_completed():
            valid = self._valid_result(result)
            if result["kind"] == "plan_review":
                valid = valid and stage == "decision" and result["observation_id"] == observation_id \
                    and result["plan_id"] == plan_id and result["plan_version"] == plan_version
            adopted_outputs = []
            if valid:
                for output in result["outputs"]:
                    if output["kind"] in {"reflection", "wonder"}:
                        entry = self._append_output(output, result["snapshot_seq"])
                        adopted_memories.append(entry.model_dump())
                        adopted_outputs.append(output)
                adopted = bool(adopted_outputs)
                reason = None if adopted else "no_usable_output"
            else:
                adopted, reason = False, "stale_context"
            self.slow.record_consumption(result, adopted=adopted, reason_code=reason)
            if adopted:
                self.adoption_counts[result["kind"]] = self.adoption_counts.get(result["kind"], 0) + 1
            else:
                self.adoption_counts["discarded"] += 1
        return adopted_memories

    def _valid_result(self, result):
        current_seq = max((entry.seq for entry in self.memory.entries), default=0)
        return (result.get("run_id") == self.memory.run_id
                and result["snapshot_seq"] <= current_seq
                and all(memory_id in self.memory.known_memory_ids
                        for memory_id in result["source_memory_ids"]))

    def _append_output(self, output, snapshot_seq):
        return self.memory.append(
            output["kind"], output["text"], output["source_step_ids"],
            output["source_observation_ids"], "generated", snapshot_seq,
            source_memory_ids=output["source_memory_ids"],
            source_stage_record_id=output["record"].record_id,
        )

    def _slow_persona(self):
        return FastLoop._persona_context(self.persona, self.persona_mode)

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

    def _require_observation(self, observation_id, stage):
        if observation_id != self.current_observation_id:
            raise ValueError(f"{stage} must use the current Brain observation")
