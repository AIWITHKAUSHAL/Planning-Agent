"""Integration tests for exhausted retries followed by successful replanning."""

import pytest

from app.agent import PlanningAgent
from app.executor import Executor
from app.llm import ModelProvider
from app.models import PlanDraft, PlannedTask, RunStatus
from app.planner import Planner
from app.state_store import StateStore


class ReplanningModel(ModelProvider):
    """Model test double that replaces an intentionally failing initial plan."""

    def __init__(self):
        """Initialize the revision counter used by assertions."""
        self.revisions = 0

    async def create_plan(self, objective):
        """Return a plan whose first task is designed to fail."""
        return PlanDraft(
            goal_summary=objective,
            reasoning="initial",
            tasks=[
                PlannedTask(
                    id="bad",
                    title="Unreliable research",
                    description="fails",
                    tool="research",
                    success_criteria="done",
                ),
                PlannedTask(
                    id="later_1",
                    title="Later analysis",
                    description="waits",
                    tool="analyze",
                    depends_on=["bad"],
                    success_criteria="done",
                ),
                PlannedTask(
                    id="later_2",
                    title="Later report",
                    description="waits",
                    tool="analyze",
                    depends_on=["later_1"],
                    success_criteria="done",
                ),
            ],
        )

    async def revise_plan(self, state, failed_task, error):
        """Return an executable fallback plan and record the revision."""
        self.revisions += 1
        return PlanDraft(
            goal_summary=state.objective,
            reasoning="use a fallback",
            tasks=[
                PlannedTask(
                    id="fallback_1",
                    title="Collect fallback data",
                    description="works",
                    tool="analyze",
                    success_criteria="done",
                ),
                PlannedTask(
                    id="fallback_2",
                    title="Check fallback data",
                    description="works",
                    tool="analyze",
                    depends_on=["fallback_1"],
                    success_criteria="done",
                ),
                PlannedTask(
                    id="fallback_3",
                    title="Prepare fallback result",
                    description="works",
                    tool="analyze",
                    depends_on=["fallback_2"],
                    success_criteria="done",
                ),
            ],
        )

    async def generate_text(self, prompt, grounded=False):
        """Return deterministic final-response text."""
        return "Final synthesized answer"


class FailureThenSuccessTools:
    """Tool test double that fails the original task and accepts replacements."""

    async def execute(self, task, dependencies):
        """Raise for the known bad task and succeed for fallback tasks."""
        if task.id == "bad":
            raise RuntimeError("simulated provider failure")
        return "fallback succeeded"


@pytest.mark.asyncio
async def test_agent_replans_after_exhausted_retry(tmp_path):
    """Verify that the agent persists and completes a revised fallback plan."""
    model = ReplanningModel()
    store = StateStore(tmp_path / "runs.db")
    agent = PlanningAgent(
        Planner(model),
        Executor(FailureThenSuccessTools(), max_retries=0),
        model,
        store,
        max_replans=1,
    )

    state = await agent.run("Complete a complex objective with recovery")

    assert state.status == RunStatus.completed
    assert state.replan_count == 1
    assert model.revisions == 1
    assert state.tasks[-1].result == "fallback succeeded"
    assert any(event.kind == "replanning" for event in state.events)
    assert store.get(state.run_id).status == RunStatus.completed
