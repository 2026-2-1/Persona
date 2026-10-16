"""Join append-only Brain evidence to the step that observed the page."""

from __future__ import annotations


def build_step_trace(steps, stages, tasks, memories, changes, wonder_draws=()):
    memory_by_id = {row.get("memory_id"): row for row in memories if row.get("memory_id")}
    removed_ids = {row.get("memory_id") for row in changes if row.get("change") == "evicted"}
    task_observations = {row.get("task_id"): row.get("observation_id") for row in tasks
                         if row.get("task_id") and row.get("observation_id")}
    wonder_observations = {row.get("wonder_task_id"): task_observations.get(row.get("parent_task_id"))
                           for row in wonder_draws if row.get("selected") and row.get("wonder_task_id")}
    trace = []
    for step in steps:
        observation_id = step.get("observation_id")
        related_tasks = [row for row in tasks if observation_id and
                         (row.get("observation_id") == observation_id or
                          wonder_observations.get(row.get("task_id")) == observation_id)]
        task_ids = {row.get("task_id") for row in related_tasks}
        related_stages = [row for row in stages if observation_id and
                          (row.get("observation_id") == observation_id or row.get("task_id") in task_ids)]
        memory_ids = dict.fromkeys([
            *(step.get("memory_ids") or []),
            *(memory_id for row in related_stages for memory_id in (row.get("source_memory_ids") or [])),
            *(memory_id for row in related_tasks for memory_id in (row.get("source_memory_ids") or [])),
        ])
        trace.append({
            "step_id": step.get("step_id"),
            "observation_id": observation_id,
            "next_observation_id": step.get("next_observation_id"),
            "stages": related_stages,
            "tasks": related_tasks,
            "memories": [{**memory_by_id[memory_id], "removed": memory_id in removed_ids}
                         if memory_id in memory_by_id else {"memory_id": memory_id, "missing": True}
                         for memory_id in memory_ids if memory_id],
            "action": step.get("action"),
            "result": step.get("result"),
            "evaluation": step.get("evaluation"),
            "verification": step.get("verification", "unknown"),
        })
    return trace
