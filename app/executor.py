from __future__ import annotations

import asyncio
from collections.abc import Callable

from app.models import AgentState, Event, TaskState, TaskStatus, utc_now
from app.tools import ToolRegistry


class TaskFailed(Exception):
    def __init__(self, task: TaskState, error: str):
        self.task = task
        self.error = error
        super().__init__(error)


class Executor:
    def __init__(self, tools: ToolRegistry, max_retries: int):
        self.tools = tools
        self.max_retries = max_retries

    async def run(self, state: AgentState, checkpoint: Callable[[AgentState], None]) -> None:
        for task in state.tasks:
            if task.status == TaskStatus.completed:
                continue
            dependencies = {item.id: item.result or "" for item in state.tasks if item.id in task.depends_on}
            incomplete = [dep for dep in task.depends_on if not dependencies.get(dep)]
            if incomplete:
                task.status = TaskStatus.skipped
                task.error = f"Dependencies did not complete: {incomplete}"
                checkpoint(state)
                raise TaskFailed(task, task.error)

            task.status = TaskStatus.running
            task.started_at = utc_now()
            state.events.append(Event(kind="task_started", task_id=task.id, message=f"Using {task.tool.value}: {task.title}"))
            checkpoint(state)

            last_error = ""
            for attempt in range(1, self.max_retries + 2):
                task.attempts = attempt
                try:
                    task.result = await self.tools.execute(task, dependencies)
                    task.status = TaskStatus.completed
                    task.error = None
                    task.finished_at = utc_now()
                    state.events.append(Event(kind="task_completed", task_id=task.id, message=f"Completed on attempt {attempt}"))
                    checkpoint(state)
                    break
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    task.error = last_error
                    state.events.append(Event(kind="task_retry", task_id=task.id, message=f"Attempt {attempt} failed: {last_error}"))
                    checkpoint(state)
                    if attempt <= self.max_retries:
                        await asyncio.sleep(min(2 ** (attempt - 1), 4))
            else:
                task.status = TaskStatus.failed
                task.finished_at = utc_now()
                checkpoint(state)
                raise TaskFailed(task, last_error)

