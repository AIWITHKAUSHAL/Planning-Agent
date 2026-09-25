"""Tests for task execution retries, results, events, and checkpoints."""

import pytest

from app.executor import Executor
from app.models import AgentState, TaskState, TaskStatus


class FlakyTools:
    """Test double that succeeds only after two transient failures."""

    def __init__(self):
        """Initialize the tool-call counter."""
        self.calls = 0

    async def execute(self, task, dependencies):
        """Fail twice, then return a stable result for retry verification."""
        self.calls += 1
        if self.calls < 3:
            raise ConnectionError("temporary outage")
        return "recovered result"


@pytest.mark.asyncio
async def test_executor_retries_and_checkpoints():
    """Verify that transient failures are retried and state is checkpointed."""
    tools = FlakyTools()
    executor = Executor(tools, max_retries=2)
    task = TaskState(id="task_1", title="Research", description="Find facts", tool="research", success_criteria="facts found")
    state = AgentState(objective="Research an important subject", tasks=[task])
    checkpoints = []

    await executor.run(state, lambda current: checkpoints.append(current.model_copy(deep=True)))

    assert tools.calls == 3
    assert task.status == TaskStatus.completed
    assert task.attempts == 3
    assert task.result == "recovered result"
    assert len([event for event in state.events if event.kind == "task_retry"]) == 2
    assert checkpoints
