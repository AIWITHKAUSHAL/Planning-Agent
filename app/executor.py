"""Dependency-aware task execution with checkpointing and retry support."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from app.models import AgentState, Event, TaskState, TaskStatus, utc_now
from app.tools import ToolRegistry


class TaskFailed(Exception):
    """Report a task that could not complete after dependency checks or retries."""

    def __init__(self, task: TaskState, error: str):
        """Store the failed task and its final error message."""
        self.task = task
        self.error = error
        super().__init__(error)


class Executor:
    """Execute planned tasks sequentially once their dependencies are available."""

    def __init__(self, tools: ToolRegistry, max_retries: int):
        """Initialize the executor.

        Args:
            tools: Registry responsible for dispatching task tool calls.
            max_retries: Additional attempts allowed after the first failure.
        """
        self.tools = tools
        self.max_retries = max_retries

    async def run(self, state: AgentState, checkpoint: Callable[[AgentState], None]) -> None:
        """Execute every unfinished task in a state and checkpoint transitions.

        Args:
            state: Mutable run state containing tasks in dependency order.
            checkpoint: Callback invoked after each meaningful state change.

        Raises:
            TaskFailed: If dependencies are unavailable or all attempts fail.
        """
        for task in state.tasks:
            if task.status == TaskStatus.completed:
                continue
            dependencies = {
                item.id: item.result or "" for item in state.tasks if item.id in task.depends_on
            }
            incomplete = [dep for dep in task.depends_on if not dependencies.get(dep)]
            if incomplete:
                task.status = TaskStatus.skipped
                task.error = f"Dependencies did not complete: {incomplete}"
                checkpoint(state)
                raise TaskFailed(task, task.error)

            task.status = TaskStatus.running
            task.started_at = utc_now()
            state.events.append(
                Event(
                    kind="task_started",
                    task_id=task.id,
                    message=f"Using {task.tool.value}: {task.title}",
                )
            )
            checkpoint(state)

            last_error = ""
            for attempt in range(1, self.max_retries + 2):
                task.attempts = attempt
                try:
                    task.result = await self.tools.execute(task, w)
                    task.status = TaskStatus.completed
                    task.error = None
                    task.finished_at = utc_now()
                    state.events.append(
                        Event(
                            kind="task_completed",
                            task_id=task.id,
                            message=f"Completed on attempt {attempt}",
                        )
                    )
                    checkpoint(state)
                    break
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    task.error = last_error
                    state.events.append(
                        Event(
                            kind="task_retry",
                            task_id=task.id,
                            message=f"Attempt {attempt} failed: {last_error}",
                        )
                    )
                    checkpoint(state)
                    if attempt <= self.max_retries:
                        await asyncio.sleep(min(2 ** (attempt - 1), 4))
            else:
                task.status = TaskStatus.failed
                task.finished_at = utc_now()
                checkpoint(state)
                raise TaskFailed(task, last_error)
